import pandas as pd
import numpy as np
import logging
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class SyntheticGammaEngine:
    """
    Computes Synthetic Gamma Exposure (GEX) levels for NQ using QQQ EOD options data.
    """
    def __init__(self, options_dir: str, underlying_path: str):
        self.options_dir = options_dir
        self.underlying_path = underlying_path
        self._load_underlying()
        self.qqq_multiplier = 100

    def _load_underlying(self):
        """Loads underlying price ratios to map QQQ to NQ"""
        try:
            self.underlying_df = pd.read_parquet(self.underlying_path)
            self.underlying_df['date'] = pd.to_datetime(self.underlying_df['date']).dt.date
            self.underlying_df = self.underlying_df.set_index('date')
            logger.info("Successfully loaded underlying price mappings.")
        except Exception as e:
            logger.error(f"Failed to load underlying data: {e}")
            self.underlying_df = None

    def get_nq_qqq_ratio(self, date: datetime, n_high: float) -> float:
        """Calculates the ratio between NQ and QQQ for strike mapping"""
        d = date.date()
        if self.underlying_df is not None and d in self.underlying_df.index:
            qqq_price = self.underlying_df.loc[d, 'close']
            if isinstance(qqq_price, pd.Series):
                qqq_price = qqq_price.iloc[0]
            return n_high / qqq_price
        return 40.0 # Default fallback

    def compute_daily_gex_profile(self, date: datetime, nq_close: float) -> Dict[str, Any]:
        """
        Computes GEX Flip levels and high gamma strike clusters for a specific date.
        """
        target_date_str = date.strftime('%Y-%m-%d')
        year = date.year
        options_file = os.path.join(self.options_dir, f"options_{year}.parquet")
        
        if not os.path.exists(options_file):
            return None

        try:
            df = pd.read_parquet(options_file, filters=[('date', '==', target_date_str)])
            if df.empty:
                return None
            
            # QQQ spot for GEX math
            d = date.date()
            if d not in self.underlying_df.index:
                return None
            spot = self.underlying_df.loc[d, 'close']
            if isinstance(spot, pd.Series): spot = spot.iloc[0]
            
            ratio = nq_close / spot
            
            # GEX calculation: Gamma * OI * Spot^2 * 100
            # Note: Call gamma is positive, Put gamma is negative for dealer net exposure typically
            df['calc_gamma'] = df.apply(lambda x: x['gamma'] if x['type'] == 'CALL' else -x['gamma'], axis=1)
            df['gex'] = df['calc_gamma'] * df['open_interest'] * (spot**2) * self.qqq_multiplier
            
            # Map strikes to NQ space
            df['nq_strike'] = df['strike'] * ratio
            
            # 1. GEX Flip (where total GEX flips sign)
            # Sort by strike and find the crossover
            df_sorted = df.groupby('nq_strike')['gex'].sum().sort_index()
            gex_cum = df_sorted.cumsum()
            
            flip_level = 0
            if not gex_cum.empty:
                # Find where it crosses zero
                zero_cross = np.where(np.diff(np.sign(gex_cum)))[0]
                if len(zero_cross) > 0:
                    flip_level = df_sorted.index[zero_cross[0]]
                else:
                    flip_level = df_sorted.index[np.abs(gex_cum).argmin()]

            # 2. Gamma Clusters (Top-N strikes by absolute GEX)
            clusters = df.groupby('nq_strike')['gex'].sum().abs().sort_values(ascending=False).head(5).index.tolist()
            
            return {
                "date": target_date_str,
                "gex_flip": float(flip_level),
                "gamma_clusters": [float(c) for c in clusters],
                "total_gex": float(df['gex'].sum()),
                "ratio": float(ratio)
            }
            
        except Exception as e:
            logger.error(f"Error computing GEX for {target_date_str}: {e}")
            return None

