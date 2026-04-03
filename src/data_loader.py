from typing import Optional
import pandas as pd
from .config import StrategyConfig

class DataLoader:
    def __init__(self, config: StrategyConfig):
        """
        Initialize the DataLoader with trading strategy configuration.
        """
        self.config = config

    def load_ohlcv(self, filepath: str) -> pd.DataFrame:
        """
        Load OHLCV data from a Parquet file and returning a normalized DataFrame.
        """
        try:
            # Assuming parquet file contains typical OHLCV columns.
            df = pd.read_parquet(filepath)
            
            # Ensure columns are normalized to lowercase standard
            df.columns = [col.lower() for col in df.columns]
            
            # Rename if necessary based on common standardizations, but primarily ensure these exist
            required_cols = {'time', 'open', 'high', 'low', 'close', 'volume'}
            if 'datetime' in df.columns and 'time' not in df.columns:
                df.rename(columns={'datetime': 'time'}, inplace=True)
            elif 'date' in df.columns and 'time' not in df.columns:
                df.rename(columns={'date': 'time'}, inplace=True)
            elif 'timestamp' in df.columns and 'time' not in df.columns:
                df.rename(columns={'timestamp': 'time'}, inplace=True)
                
            missing_cols = required_cols - set(df.columns)
            if missing_cols:
                raise ValueError(f"Parquet file {filepath} is missing required columns: {missing_cols}")
                
            df.set_index('time', inplace=True)
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            
            return df
        except Exception as e:
            raise RuntimeError(f"Failed to load data from {filepath}: {e}")
