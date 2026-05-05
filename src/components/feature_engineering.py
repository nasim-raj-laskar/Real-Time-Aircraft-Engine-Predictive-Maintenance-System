import numpy as np
import pandas as pd
import boto3
from pathlib import Path
from sklearn.model_selection import GroupShuffleSplit
from src.entity.config_entity import DataFeatureEngineeringConfig
from src.logging.logger import logging
from src.constants import *

class FeatureEngineering:
    def __init__(self, config: DataFeatureEngineeringConfig):
        self.config = config
        self.s3 = boto3.client("s3")

    def load_data(self):
        logging.info("Loading Silver layer data...")

        train = pd.read_parquet(self.config.processed_dir / "train_processed.parquet")
        test = pd.read_parquet(self.config.processed_dir / "test_processed.parquet")

        logging.info(f"Train: {train.shape}, Test: {test.shape}")
        return train, test

    def build_sequences(self, df, feature_cols):
        X, y = [], []

        for _, eng in df.groupby('unit'):
            eng = eng.sort_values('cycle')
            data = eng[feature_cols].values
            labels = eng['RUL'].values

            for i in range(len(data) - self.config.window_size + 1):
                X.append(data[i:i+self.config.window_size])
                y.append(labels[i+self.config.window_size-1])

        return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)
    
    def build_last_sequences(self, df, feature_cols):
        X, y = [], []

        for _, eng in df.groupby('unit'):
            eng = eng.sort_values('cycle')
            data = eng[feature_cols].values

            if len(data) >= self.config.window_size:
                X.append(data[-self.config.window_size:])
            else:
                pad = np.zeros((self.config.window_size - len(data), len(feature_cols)))
                X.append(np.vstack([pad, data]))

            y.append(eng['RUL'].iloc[-1])

        return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)
        
    def split_data(self, train_df):
        logging.info("Splitting data (Group-aware)...")

        gss = GroupShuffleSplit(
            n_splits=1,
            test_size=self.config.test_size,
            random_state=self.config.random_state
        )

        tr_idx, val_idx = next(gss.split(train_df, groups=train_df['unit']))

        return train_df.iloc[tr_idx], train_df.iloc[val_idx]

    def run(self):
        logging.info("========== FEATURE ENGINEERING STARTED ==========")

        train, test = self.load_data()

        feature_cols = [col for col in train.columns if col.startswith("s")]

        # ---------------- SPLIT ----------------
        train_split, val_split = self.split_data(train)

        # ---------------- SEQUENCES ----------------
        logging.info("Building training sequences...")
        X_train, y_train_raw = self.build_sequences(train_split, feature_cols)

        logging.info("Building validation sequences...")
        X_val, y_val_raw = self.build_sequences(val_split, feature_cols)

        logging.info("Building test sequences...")
        X_test, y_test_raw = self.build_last_sequences(test, feature_cols)

        # ---------------- NORMALIZATION ----------------
        logging.info("Normalizing targets...")

        y_train = (y_train_raw / self.config.rul_clip).astype(np.float32)
        y_val = (y_val_raw / self.config.rul_clip).astype(np.float32)
        y_test = np.clip(y_test_raw, 0, self.config.rul_clip).astype(np.float32)

        logging.info(f"Shapes → X_train: {X_train.shape}, X_val: {X_val.shape}, X_test: {X_test.shape}")

        # ---------------- SAVE ----------------
        np.save(self.config.output_dir / self.config.X_train, X_train)
        np.save(self.config.output_dir / self.config.y_train, y_train)

        np.save(self.config.output_dir / self.config.X_val, X_val)
        np.save(self.config.output_dir / self.config.y_val, y_val)

        np.save(self.config.output_dir / self.config.X_test, X_test)
        np.save(self.config.output_dir / self.config.y_test, y_test)

        # ---------------- SAVE METADATA ----------------
        from src.utils.common import save_json

        save_json(self.config.output_dir / "feature_config.json", {
            "window_size": self.config.window_size,
            "features": feature_cols,
            "rul_clip": self.config.rul_clip,
            "scaler_path": "artifacts/scaler.pkl"
        })

        logging.info("Uploading Gold layer to S3...")

        for file in [
            self.config.X_train, self.config.y_train,
            self.config.X_val, self.config.y_val,
            self.config.X_test, self.config.y_test
        ]:
            self.s3.upload_file(
                str(self.config.output_dir / file),
                self.config.s3_bucket,
                f"{self.config.s3_gold_prefix}{file}"
            )
            logging.info(f"Uploaded {file}")

        logging.info("========== FEATURE ENGINEERING COMPLETED ==========\n")