import pandas as pd
import numpy as np
from typing import Dict, Any, List
from src.execution import TradeSetup, Direction

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
            clusters = np.array(g['gamma_clusters'])
            if len(clusters) > 0:
                features['nearest_cluster_dist'] = np.min(np.abs(clusters - setup.entry_price))
            else:
                features['nearest_cluster_dist'] = 999.0
        else:
            features['gex_flip_dist'] = 0.0
            features['total_gex'] = 0.0
            features['gex_regime'] = 0
            features['nearest_cluster_dist'] = 999.0

        return features
