from pathlib import Path
from src.utils.common import *
from src.entity.config_entity import *
from src.constants import *
from dotenv import load_dotenv
import os

load_dotenv()

class ConfigurationManager:
    def __init__(
        self,
        config_filepath=CONFIG,
        params_filepath=PARAMS,
        schema_filepath=SCHEMA,
        models_filepath=MODELS):

        self.config = read_yaml(config_filepath)
        self.params = read_yaml(params_filepath)
        self.schema = read_yaml(schema_filepath)
        self.models = read_yaml(models_filepath)

        create_directories([self.config.artifacts_root])

    def get_data_ingestion_config(self) -> DataIngestionConfig:
        config = self.config.data_ingestion

        create_directories([config.root_dir, config.local_data_dir])

        data_ingestion_config = DataIngestionConfig(
            root_dir=Path(config.root_dir),
            s3_bucket = os.getenv("AWS_S3_BUCKET") or config.s3_bucket,
            s3_keys=dict(config.s3_keys),
            local_data_dir=Path(config.local_data_dir)
        )

        return data_ingestion_config
    
    def get_data_validation_config(self) -> DataValidationConfig:
        config = self.config.data_validation
        schema = self.schema.data_validation

        create_directories([config.root_dir])

        data_validation_config = DataValidationConfig(
            root_dir=Path(config.root_dir),
            data_dir=Path(config.data_dir),
            status_file=Path(config.status_file),
            expected_columns=schema.expected_columns,
            column_names=schema.column_names
        )

        return data_validation_config