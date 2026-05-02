import boto3
from pathlib import Path
from src.entity.config_entity import DataIngestionConfig
from src.logging.logger import logging


class DataIngestion:
    def __init__(self, config: DataIngestionConfig):
        self.config = config
        self.s3 = boto3.client("s3")

    def download_file(self, key: str, local_path: Path):
        if local_path.exists():
            logging.info(f"Skipping existing file: {local_path}")
            return

        self.s3.download_file(
            self.config.s3_bucket,
            key,
            str(local_path)
        )
        logging.info(f"Downloaded: {key} → {local_path}")

    def run(self):
        local_paths = {}

        for name, key in self.config.s3_keys.items():
            local_path = self.config.local_data_dir / Path(key).name

            self.download_file(key, local_path)

            local_paths[name] = local_path

        return local_paths