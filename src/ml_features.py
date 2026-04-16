import pandas as pd
import numpy as np
from typing import Dict, Any, List
from src.execution import TradeSetup, Direction


def nearest_cluster_distance(entry_price: float, gamma_context: Dict[str, Any]) -> float:
    """Lightweight helper for rule filters that only need cluster distance."""
    if not gamma_context:
        return 999.0

    clusters = gamma_context.get('gamma_clusters')
    if not clusters:
        return 999.0

    clusters_arr = np.asarray(clusters, dtype=np.float64)
    if clusters_arr.size == 0:
        return 999.0

    return float(np.min(np.abs(clusters_arr - entry_price)))

class FeatureExtractor:
    """
    Extracts features for ML training from trade setups and market context.
    """
    def __init__(self):
        pass

    def get_features(self, setup: TradeSetup, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts a flat feature dictionary for a given trade setup.
        
        Args:
            setup: The TradeSetup object.
            context: Dictionary containing market state (gamma levels, IV, etc.)
        """
        features = {}
        
        # 1. Trade Setup Basic Features
        features['direction'] = 1 if setup.direction == Direction.LONG else 0
        features['entry_price'] = setup.entry_price
        features['risk_points'] = abs(setup.entry_price - setup.stop_price)
        features['target_points'] = abs(setup.target_price - setup.entry_price)
        features['risk_reward'] = setup.risk_reward
        features['momentum_score'] = setup.momentum_score
        
        # 2. Time Features
        features['hour'] = setup.created_at.hour
        features['day_of_week'] = setup.created_at.weekday()
        
        # 3. Gamma / Options Features (Synthetic)
        if 'gamma' in context and context['gamma']:
            g = context['gamma']
            features['gex_flip_dist'] = setup.entry_price - g['gex_flip']
            features['total_gex'] = g['total_gex']
            features['gex_regime'] = 1 if g['total_gex'] > 0 else 0
            
            # Distance to nearest cluster
            features['nearest_cluster_dist'] = nearest_cluster_distance(setup.entry_price, g)
        else:
            features['gex_flip_dist'] = 0.0
            features['total_gex'] = 0.0
            features['gex_regime'] = 0
            features['nearest_cluster_dist'] = 999.0

        return features
