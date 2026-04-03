import pandas as pd
import numpy as np

class StrategyLogic:
    def __init__(self, pivot_lookback: int = 10, sweep_max_lookback: int = 20):
        self.pivot_lookback = pivot_lookback
        self.sweep_max_lookback = sweep_max_lookback

    def detect_sweeps(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify Liquidity Sweeps using vectorized operations.
        """
        df = df.copy()
        
        # Dynamic BSL and SSL levels: 
        # rolling max/min over pivot_lookback bars, shifted by 1 to exclude current bar
        df['active_bsl_level'] = df['high'].rolling(window=self.pivot_lookback).max().shift(1)
        df['active_ssl_level'] = df['low'].rolling(window=self.pivot_lookback).min().shift(1)
        
        # BSL Sweeps
        df['bsl_wick_sweep'] = df['high'] > df['active_bsl_level']
        df['bsl_body_sweep'] = df['close'] > df['active_bsl_level']
        
        # SSL Sweeps
        df['ssl_wick_sweep'] = df['low'] < df['active_ssl_level']
        df['ssl_body_sweep'] = df['close'] < df['active_ssl_level']
        
        return df

    def detect_fvgs(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Identify Fair Value Gaps (FVGs).
        Bullish FVG: n-2 high < n low
        Bearish FVG: n-2 low > n high
        """
        df = df.copy()
        
        # Bullish FVG
        df['fvg_bull'] = df['high'].shift(2) < df['low']
        # The gap is between the high of n-2 and the low of n
        df['fvg_bull_top'] = df['low']
        df['fvg_bull_bottom'] = df['high'].shift(2)
        
        # Bearish FVG
        df['fvg_bear'] = df['low'].shift(2) > df['high']
        # The gap is between the low of n-2 and the high of n
        df['fvg_bear_top'] = df['low'].shift(2)
        df['fvg_bear_bottom'] = df['high']
        
        return df

    def detect_zones(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Groups consecutive same-direction FVGs.
        Establishes continuous state tracking for zone borders.
        """
        df = df.copy()
        
        bull_top, bull_bot = np.nan, np.nan
        bear_top, bear_bot = np.nan, np.nan
        
        active_bull_zone_tops = np.full(len(df), np.nan)
        active_bull_zone_bottoms = np.full(len(df), np.nan)
        active_bear_zone_tops = np.full(len(df), np.nan)
        active_bear_zone_bottoms = np.full(len(df), np.nan)
        
        fvg_bull_vals = df['fvg_bull'].values
        fvg_bull_tops = df['fvg_bull_top'].values
        fvg_bull_bots = df['fvg_bull_bottom'].values
        
        fvg_bear_vals = df['fvg_bear'].values
        fvg_bear_tops = df['fvg_bear_top'].values
        fvg_bear_bots = df['fvg_bear_bottom'].values
        
        closes = df['close'].values
        
        for i in range(len(df)):
            # Bullish Stacks tracking
            if not np.isnan(bull_top):
                # Gap invalidated if body closes below the zone bottom
                if closes[i] < bull_bot: 
                    bull_top, bull_bot = np.nan, np.nan
            
            if fvg_bull_vals[i]:
                if np.isnan(bull_top):
                    bull_top = fvg_bull_tops[i]
                    bull_bot = fvg_bull_bots[i]
                else: # Stack
                    bull_top = max(bull_top, fvg_bull_tops[i])
                    bull_bot = min(bull_bot, fvg_bull_bots[i])
                    
            active_bull_zone_tops[i] = bull_top
            active_bull_zone_bottoms[i] = bull_bot
            
            # Bearish Stacks tracking
            if not np.isnan(bear_top):
                if closes[i] > bear_top: 
                    bear_top, bear_bot = np.nan, np.nan
                    
            if fvg_bear_vals[i]:
                if np.isnan(bear_top):
                    bear_top = fvg_bear_tops[i]
                    bear_bot = fvg_bear_bots[i]
                else: # Stack
                    bear_top = max(bear_top, fvg_bear_tops[i])
                    bear_bot = min(bear_bot, fvg_bear_bots[i])
                    
            active_bear_zone_tops[i] = bear_top
            active_bear_zone_bottoms[i] = bear_bot
            
        df['active_bull_zone_top'] = active_bull_zone_tops
        df['active_bull_zone_bottom'] = active_bull_zone_bottoms
        df['active_bear_zone_top'] = active_bear_zone_tops
        df['active_bear_zone_bottom'] = active_bear_zone_bottoms
        
        return df
