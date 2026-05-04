import pandas as pd
import numpy as np
import boto3
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler
from src.entity.config_entity import DataTransformationConfig
from src.logging.logger import logging
import joblib
from src.constants import *


class DataTransformation:
    def __init__(self, config: DataTransformationConfig):
        self.config = config
        self.s3 = boto3.client("s3")

    def load_data(self):
        logging.info("Loading raw data...")

        train = pd.read_csv(self.config.data_dir / "train_FD001.txt", sep=r"\s+", header=None)
        test = pd.read_csv(self.config.data_dir / "test_FD001.txt", sep=r"\s+", header=None)
        rul = pd.read_csv(self.config.data_dir / "RUL_FD001.txt", header=None)

        logging.info(f"Train shape: {train.shape}, Test shape: {test.shape}, RUL shape: {rul.shape}")

        return train, test, rul

    def assign_columns(self, df):
        cols = ['unit','cycle','os1','os2','os3'] + [f's{i}' for i in range(1, 22)]
        df.columns = cols
        return df

    def add_rul(self, df):
        max_cycle = df.groupby('unit')['cycle'].transform('max')
        df['RUL'] = (max_cycle - df['cycle']).clip(upper=self.config.rul_clip)
        return df

    def transform(self):
        train, test, rul = self.load_data()

        train = self.assign_columns(train)
        test = self.assign_columns(test)

        logging.info("Dropping unnecessary columns...")
        train.drop(columns=self.config.drop_columns, inplace=True)
        test.drop(columns=self.config.drop_columns, inplace=True)

        logging.info("Adding RUL to train...")
        train = self.add_rul(train)

        logging.info("Attaching RUL to test...")
        last_cycles = test.groupby('unit')['cycle'].max().reset_index()
        last_cycles['RUL'] = rul[0].values
        test = test.merge(last_cycles[['unit','RUL']], on='unit', how='left')

        logging.info("Scaling features...")
        scaler = MinMaxScaler()

        train[self.config.keep_sensors] = scaler.fit_transform(train[self.config.keep_sensors])
        test[self.config.keep_sensors] = scaler.transform(test[self.config.keep_sensors])

        joblib.dump(scaler, self.config.scaler_path)
        logging.info(f"Scaler saved at {self.config.scaler_path}")

        return train, test

    def save_and_upload(self, train, test):
        train_path = self.config.processed_dir / self.config.train_output
        test_path = self.config.processed_dir / self.config.test_output

        logging.info("Saving parquet files locally...")
        train.to_parquet(train_path)
        test.to_parquet(test_path)

        logging.info("Uploading to S3 (Silver layer)...")

        self.s3.upload_file(str(train_path), self.config.s3_bucket,
                           f"{self.config.s3_silver_prefix}{self.config.train_output}")

        self.s3.upload_file(str(test_path), self.config.s3_bucket,
                           f"{self.config.s3_silver_prefix}{self.config.test_output}")

        logging.info("Upload completed.")

    def run(self):
        logging.info("========== DATA TRANSFORMATION STARTED ==========")

        train, test = self.transform()
        self.save_and_upload(train, test)

        logging.info("========== DATA TRANSFORMATION COMPLETED ==========\n")