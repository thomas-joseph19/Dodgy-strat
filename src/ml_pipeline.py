import pandas as pd
import numpy as np
import xgboost as xgb
import optuna
import os
import json
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score, precision_score, recall_score
from src.ml_visualizations import MLVisualizer

from tqdm import tqdm

class MLPipeline:
    def __init__(self, data_path: str, output_dir: str, 
                 train_start: str = None, train_end: str = None, 
                 test_start: str = None, test_end: str = None):
        self.data_path = data_path
        self.output_dir = output_dir
        self.train_start = train_start
        self.train_end = train_end
        self.test_start = test_start
        self.test_end = test_end
        self.visualizer = MLVisualizer(output_dir)

    def run(self):
        if not os.path.exists(self.data_path):
            print(f"Data not found at {self.data_path}")
            return

        df = pd.read_csv(self.data_path)
        
        # Check if timestamp exists before trying to split by date
        has_time = 'timestamp' in df.columns
        if has_time:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        elif (self.train_start or self.train_end or self.test_start or self.test_end):
            print("ERROR: features.csv missing 'timestamp' column. Re-run backtest to update data.")
            return
        
        if df.empty or len(df) < 5:
            print("Not enough data for ML training.")
            return

        # 1. Handle Training Split
        train_df = df.copy()
        if has_time:
            if self.train_start:
                train_df = train_df[train_df['timestamp'] >= pd.to_datetime(self.train_start)]
            if self.train_end:
                train_df = train_df[train_df['timestamp'] <= pd.to_datetime(self.train_end)]
        
        if not self.train_start and not self.train_end:
            split_idx = int(len(df) * 0.8)
            train_df = df.iloc[:split_idx]

        # 2. Handle Testing Split
        test_df = df.copy()
        if has_time:
            if self.test_start:
                test_df = test_df[test_df['timestamp'] >= pd.to_datetime(self.test_start)]
            if self.test_end:
                test_df = test_df[test_df['timestamp'] <= pd.to_datetime(self.test_end)]
            
        if not self.test_start and not self.test_end:
            if has_time and self.train_end:
                test_df = df[df['timestamp'] > pd.to_datetime(self.train_end)]
            else:
                test_df = df.iloc[int(len(df) * 0.8):]

        if train_df.empty or test_df.empty:
            print(f"Split Error: Train Samples: {len(train_df)}, Test Samples: {len(test_df)}")
            return

        # Prepare features
        drop_cols = ['setup_id', 'label', 'timestamp']
        X_train = train_df.drop(columns=[c for c in drop_cols if c in train_df.columns])
        y_train = train_df['label']
        X_test = test_df.drop(columns=[c for c in drop_cols if c in test_df.columns])
        y_test = test_df['label']

        if has_time:
            print(f"Training Range: {train_df['timestamp'].min()} to {train_df['timestamp'].max()} ({len(train_df)} samples)")
            print(f"Testing Range:  {test_df['timestamp'].min()} to {test_df['timestamp'].max()} ({len(test_df)} samples)")
        else:
            print(f"Dataset split by index: {len(train_df)} train, {len(test_df)} test.")

        def objective(trial):
            params = {
                'verbosity': 0,
                'objective': 'binary:logistic',
                'eval_metric': 'auc',
                'lambda': trial.suggest_float('lambda', 1e-8, 1.0, log=True),
                'alpha': trial.suggest_float('alpha', 1e-8, 1.0, log=True),
                'max_depth': trial.suggest_int('max_depth', 3, 9),
                'eta': trial.suggest_float('eta', 1e-3, 0.5, log=True),
                'gamma': trial.suggest_float('gamma', 1e-8, 1.0, log=True),
            }

            dtrain = xgb.DMatrix(X_train, label=y_train)
            dtest = xgb.DMatrix(X_test, label=y_test)
            
            model = xgb.train(params, dtrain, num_boost_round=100)
            preds = model.predict(dtest)
            
            if len(np.unique(y_test)) > 1:
                return roc_auc_score(y_test, preds)
            return 0.5

        # Progress bar configuration
        n_trials = 50
        pbar = tqdm(total=n_trials, desc="Optimizing XGBoost Parameters")
        
        def callback(study, trial):
            pbar.update(1)
            pbar.set_postfix(best_auc=f"{study.best_value:.4f}")

        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials, callbacks=[callback])
        pbar.close()

        best_params = study.best_params
        best_params.update({'objective': 'binary:logistic', 'eval_metric': 'auc'})

        # Final Training
        dtrain_full = xgb.DMatrix(X_train, label=y_train)
        dtest_full = xgb.DMatrix(X_test, label=y_test)
        final_model = xgb.train(best_params, dtrain_full, num_boost_round=150)

        # Metrics for visualization
        test_preds = final_model.predict(dtest_full)
        test_class = [1 if p > 0.5 else 0 for p in test_preds]
        
        metrics = {
            'roc_auc': roc_auc_score(y_test, test_preds) if len(np.unique(y_test)) > 1 else 0.5,
            'precision': precision_score(y_test, test_class, zero_division=0),
            'recall': recall_score(y_test, test_class, zero_division=0),
            'best_trial': study.best_trial.number
        }

        fi = final_model.get_score(importance_type='gain')
        fi_full = {col: fi.get(col, 0.0) for col in X_train.columns}

        os.makedirs(self.output_dir, exist_ok=True)
        final_model.save_model(os.path.join(self.output_dir, "xgboost_model.json"))
        
        # Save readable parameters
        with open(os.path.join(self.output_dir, "best_params.json"), 'w') as f:
            json.dump(best_params, f, indent=4)
        
        dash_path = self.visualizer.generate_html_report(metrics, fi_full)
        print(f"\nDone. Best AUC: {study.best_trial.value:.4f}")
        print(f"Dashboard: {dash_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True)
    parser.add_argument("--out", type=str, default="ml_output")
    parser.add_argument("--train-start", type=str, help="YYYY-MM-DD")
    parser.add_argument("--train-end", type=str, help="YYYY-MM-DD")
    parser.add_argument("--test-start", type=str, help="YYYY-MM-DD")
    parser.add_argument("--test-end", type=str, help="YYYY-MM-DD")
    args = parser.parse_args()
    
    pipeline = MLPipeline(args.data, args.out, 
                          args.train_start, args.train_end, 
                          args.test_start, args.test_end)
    pipeline.run()
