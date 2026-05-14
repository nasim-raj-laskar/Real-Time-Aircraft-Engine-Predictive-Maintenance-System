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
        models_filepath=MODELS,
        transform_filepath=TRANSFORM,
        features_filepath=FEATURES,
        registor_filepath=REGISTOR
):

        self.config = read_yaml(config_filepath)
        self.params = read_yaml(params_filepath)
        self.schema = read_yaml(schema_filepath)
        self.models = read_yaml(models_filepath)
        self.transform = read_yaml(transform_filepath)
        self.features = read_yaml(features_filepath)
        self.registor = read_yaml(registor_filepath)

        create_directories([self.config.artifacts_root])

#------------------------------Data Ingestion Configurations---------------------------------
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
    
#------------------------------Data Validation Configurations---------------------------------
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
    
#------------------------------Data Transformation Configurations---------------------------------
    def get_data_transformation_config(self) -> DataTransformationConfig:
        config = self.config.data_transformation
        transform = self.transform.transformation

        create_directories([config.root_dir, config.processed_dir])

        data_transformation_config=DataTransformationConfig(
            root_dir=Path(config.root_dir),
            data_dir=Path(config.data_dir),
            processed_dir=Path(config.processed_dir),
            s3_bucket=os.getenv("AWS_S3_BUCKET"),
            s3_silver_prefix=config.s3_silver_prefix,
            train_output=config.train_output,
            test_output=config.test_output,
            scaler_path=Path(config.scaler_path),
            drop_columns=transform.drop_columns,
            keep_sensors=transform.keep_sensors,
            rul_clip=transform.rul_clip
        )

        return data_transformation_config
    
#------------------------------Data Feature Engineering Configurations---------------------------------
    def get_data_feature_engineering_config(self) -> DataFeatureEngineeringConfig:
        config = self.config.data_feature_engineering
        features = self.features.features
        transform = self.transform.transformation

        create_directories([config.root_dir, config.output_dir])

        data_feature_engineering_config = DataFeatureEngineeringConfig(
            root_dir=Path(config.root_dir),
            processed_dir=Path(config.processed_dir),
            output_dir=Path(config.output_dir),
            s3_bucket=os.getenv("AWS_S3_BUCKET"),
            s3_gold_prefix=config.s3_gold_prefix,
            X_train=config.X_train,
            y_train=config.y_train,
            X_val=config.X_val,
            y_val=config.y_val,
            X_test=config.X_test,
            y_test=config.y_test,
            rul_clip=transform.rul_clip,
            window_size=features.window_size,
            test_size=features.test_size,
            random_state=features.random_state
        )

        return data_feature_engineering_config
    
#------------------------------Model Trainer Configurations---------------------------------
    def get_model_trainer_config(self) -> ModelTrainerConfig:
        config = self.config.model_trainer
        model = self.models.gru_model
        params = self.params.training

        create_directories([config.root_dir])

        model_trainer_config = ModelTrainerConfig(
            root_dir=Path(config.root_dir),
            gold_dir=Path(config.gold_dir),
            model_path=Path(config.model_path),
            history_path=Path(config.history_path),
            s3_bucket=os.getenv("AWS_S3_BUCKET"),
            s3_artifact_prefix=config.s3_artifact_prefix,
            gru_units=model.gru_units,
            dense_units=model.dense_units,
            dropout_rates=model.dropout_rates,
            l2_regularization=model.l2_regularization,
            epochs=params.epochs,
            batch_size=params.batch_size,
            learning_rate=params.learning_rate,
            early_stopping_patience=params.early_stopping_patience,
            reduce_lr_patience=params.reduce_lr_patience,
            reduce_lr_factor=params.reduce_lr_factor,
            min_lr=params.min_lr
        )

        return model_trainer_config

#------------------------------Model Evaluation Configurations---------------------------------
    def get_model_evaluation_config(self) -> ModelEvaluationConfig:
        config = self.config.model_evaluation

        create_directories([config.root_dir])

        model_evaluation_config = ModelEvaluationConfig(
            root_dir=Path(config.root_dir),
            model_path=Path(config.model_path),
            gold_dir=Path(config.gold_dir),
            metrics_path=Path(config.metrics_path),
            results_path=Path(config.results_path),
            confusion_matrix_path=Path(config.confusion_matrix_path),
            prediction_plot_path=Path(config.prediction_plot_path),
            error_distribution_path=Path(config.error_distribution_path),
            s3_bucket=os.getenv("AWS_S3_BUCKET"),
            s3_artifact_prefix=config.s3_artifact_prefix
        )

        return model_evaluation_config
    
#------------------------------Model Registration Configurations---------------------------------
    def get_model_registry_config(self) -> ModelRegistryConfig:
        config = self.config.model_registry
        registry = self.registor

        create_directories([config.root_dir])

        model_registry_config = ModelRegistryConfig(
            root_dir=Path(config.root_dir),
            model_path=Path(config.model_path),
            gold_dir=Path(config.gold_dir),
            metrics_path=Path(config.metrics_path),
            registered_model_name=registry.registered_model_name,
            rmse_threshold=registry.promotion_thresholds.rmse,
            nasa_threshold=registry.promotion_thresholds.nasa_score,
            stage=registry.stage,
            s3_bucket=os.getenv("AWS_S3_BUCKET"),
            s3_artifact_prefix=config.s3_artifact_prefix
        )

        return model_registry_config