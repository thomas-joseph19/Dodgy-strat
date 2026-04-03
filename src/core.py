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
