import os
from dataclasses import dataclass, field

@dataclass
class StrategyConfig:
    # Liquidity detection tolerances
    tolerance: float = field(default_factory=lambda: float(os.getenv("IFVG_TOLERANCE", "0.01")))
    
    # Validation timeframe settings
    timeframe: str = field(default_factory=lambda: os.getenv("IFVG_TIMEFRAME", "1Min"))
    
    # Momentum and Risk constraints
    high_momentum_threshold: float = field(default_factory=lambda: float(os.getenv("IFVG_HIGH_MOMENTUM", "0.7")))
    high_rr_threshold: float = field(default_factory=lambda: float(os.getenv("IFVG_HIGH_RR", "8.0")))
    
    # Feature flags for stops
    default_stop_type: str = field(default_factory=lambda: os.getenv("IFVG_DEFAULT_STOP", "fail_stop"))
    
    # Core Mechanics configurations
    pivot_lookback: int = field(default_factory=lambda: int(os.getenv("IFVG_PIVOT_LOOKBACK", "10")))
    sweep_max_lookback: int = field(default_factory=lambda: int(os.getenv("IFVG_SWEEP_MAX_LOOKBACK", "20")))
