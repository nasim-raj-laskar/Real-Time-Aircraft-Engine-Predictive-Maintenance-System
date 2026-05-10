import boto3
from pathlib import Path
from src.logging.logger import logging


class S3Client:
    def __init__(self):
        self.client = boto3.client("s3")

    def upload(self, local_path: str | Path, bucket: str, s3_key: str):
        logging.info(f"Uploading {local_path} → s3://{bucket}/{s3_key}")
        self.client.upload_file(str(local_path), bucket, s3_key)
        logging.info(f"Upload complete: s3://{bucket}/{s3_key}")

    def download(self, bucket: str, s3_key: str, local_path: str | Path):
        logging.info(f"Downloading s3://{bucket}/{s3_key} → {local_path}")
        self.client.download_file(bucket, s3_key, str(local_path))
        logging.info(f"Download complete: {local_path}")
