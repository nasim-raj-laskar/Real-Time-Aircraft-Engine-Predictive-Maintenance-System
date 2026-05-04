import pandas as pd
import numpy as np
from pathlib import Path
from src.entity.config_entity import DataValidationConfig
from src.logging.logger import logging
from src.utils.common import save_json


class DataValidation:
    def __init__(self, config: DataValidationConfig):
        self.config = config

    # MAIN FILE VALIDATION (train/test)
    def validate_main_file(self, df: pd.DataFrame, file_name: str):
        logging.info(f"[{file_name}] Checking column count...")
        if df.shape[1] != self.config.expected_columns:
            raise Exception(f"{file_name}: Expected {self.config.expected_columns} columns, got {df.shape[1]}")
        logging.info(f"[{file_name}] Column count OK ({df.shape[1]})")

        # Assign column names
        df.columns = self.config.column_names
        logging.info(f"[{file_name}] Checking numeric data types...")
        if not all(df.dtypes.apply(lambda x: np.issubdtype(x, np.number))):
            raise Exception(f"{file_name}: Non-numeric values found")

        logging.info(f"[{file_name}] All columns numeric")
        logging.info(f"[{file_name}] Checking cycle monotonicity per unit...")

        for unit, group in df.groupby("unit"):
            if not group["cycle"].is_monotonic_increasing:
                raise Exception(f"{file_name}: Cycle not increasing for unit {unit}")
        logging.info(f"[{file_name}] Cycle monotonicity OK")

    # RUL FILE VALIDATION
    def validate_rul_file(self, df: pd.DataFrame, file_name: str):
        logging.info(f"[{file_name}] Checking RUL structure...")
        if df.shape[1] != 1:
            raise Exception(f"{file_name}: Expected 1 column, got {df.shape[1]}")
        logging.info(f"[{file_name}] Column count OK (1)")
        if not np.issubdtype(df[0].dtype, np.number):
            raise Exception(f"{file_name}: Non-numeric RUL values")
        if (df[0] < 0).any():
            raise Exception(f"{file_name}: Negative RUL values found")
        logging.info(f"[{file_name}] RUL values valid")

    # FILE ROUTER
    def validate_file(self, file_path: Path):
        file_name = file_path.name
        logging.info(f"Starting validation for: {file_name}")
        df = pd.read_csv(file_path, sep=r"\s+", header=None)
        logging.info(f"[{file_name}] Shape: {df.shape}")
        if "RUL" in file_name.upper():
            self.validate_rul_file(df, file_name)
        else:
            self.validate_main_file(df, file_name)
        logging.info(f"{file_name} validation passed\n")
    # PIPELINE ENTRY
    def run(self):
        try:

            files = list(Path(self.config.data_dir).glob("*.txt"))

            if not files:
                raise Exception("No data files found for validation")

            logging.info(f"Found {len(files)} files for validation")

            for file in files:
                self.validate_file(file)

            save_json(self.config.status_file, {
                "status": "passed",
                "validated_files": [f.name for f in files]
            })

            logging.info("Data Validation completed successfully")

        except Exception as e:
            save_json(self.config.status_file, {
                "status": "failed",
                "error": str(e)
            })

            logging.error("Data Validation FAILED")
            logging.error(f"Reason: {e}")

            raise e