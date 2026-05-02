from dataclasses import dataclass
from pathlib import Path
from typing import Dict

@dataclass
class DataIngestionConfig:
    root_dir: Path
    s3_bucket: str
    s3_keys: Dict[str, str]
    local_data_dir: Path