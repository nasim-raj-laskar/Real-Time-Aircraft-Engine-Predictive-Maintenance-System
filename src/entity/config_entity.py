from dataclasses import dataclass
from pathlib import Path
from typing import Dict,List

@dataclass
class DataIngestionConfig:
    root_dir: Path
    s3_bucket: str
    s3_keys: Dict[str, str]
    local_data_dir: Path

@dataclass
class DataValidationConfig:
    root_dir: Path
    data_dir: Path
    status_file: Path
    expected_columns: int
    column_names: list

@dataclass
class DataTransformationConfig:
    root_dir: Path
    data_dir: Path
    processed_dir: Path
    s3_bucket: str
    s3_silver_prefix: str
    train_output: str
    test_output: str
    scaler_path: Path
    drop_columns: List[str]
    keep_sensors: List[str]
    rul_clip: int