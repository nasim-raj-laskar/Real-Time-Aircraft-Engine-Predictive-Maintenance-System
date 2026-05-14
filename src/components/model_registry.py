import json
import mlflow
import mlflow.tensorflow
import tensorflow as tf
from mlflow.tracking import MlflowClient
from mlflow.models.signature import infer_signature
import numpy as np
from pathlib import Path
from src.entity.config_entity import ModelRegistryConfig
from src.logging.logger import logging
from src.cloud.s3 import S3Client


class ModelRegistry:
    def __init__(self, config: ModelRegistryConfig):
        self.config = config
        self.client = MlflowClient()
        self.s3 = S3Client()

    # LOAD METRICS
    def load_metrics(self):
        logging.info("Loading evaluation metrics...")
        with open(self.config.metrics_path) as f:
            metrics = json.load(f)
        rmse = metrics["rmse"]
        nasa = metrics["nasa_score"]
        logging.info(f"RMSE: {rmse}")
        logging.info(f"NASA Score: {nasa}")
        return rmse, nasa

    # PROMOTION POLICY CHECK
    def should_promote(self, rmse, nasa):
        logging.info("Checking promotion thresholds...")

        if (
            rmse <= self.config.rmse_threshold
            and nasa <= self.config.nasa_threshold
        ):
            logging.info("Model PASSED promotion thresholds")
            return True

        logging.warning("Model FAILED promotion thresholds")
        return False

    # REGISTER MODEL TO MLFLOW
    def register_model(self):
        logging.info("Registering model to MLflow...")

        # Load model and test data for signature
        model = tf.keras.models.load_model(self.config.model_path)
        X_test = np.load(self.config.gold_dir / "X_test.npy")
        
        # Generate sample prediction for signature
        sample_pred = model.predict(X_test[:1], verbose=0)
        signature = infer_signature(X_test[:1], sample_pred)

        # Log model to MLflow
        model_info = mlflow.tensorflow.log_model(
            model=model,
            artifact_path="model",
            signature=signature,
            registered_model_name=self.config.registered_model_name
        )

        logging.info(f"Model logged to MLflow: {model_info.model_uri}")

        # Get the registered model version
        registered_model = self.client.get_registered_model(self.config.registered_model_name)
        latest_version = registered_model.latest_versions[-1].version

        logging.info(f"Registered model version: {latest_version}")

        return latest_version

    # PROMOTE MODEL TO STAGE
    def promote_model(self, version):
        logging.info(f"Promoting version {version} to {self.config.stage}")

        self.client.transition_model_version_stage(
            name=self.config.registered_model_name,
            version=version,
            stage=self.config.stage
        )

        logging.info("Promotion successful")

    # UPLOAD ARTIFACTS TO S3
    def upload_to_s3(self):
        logging.info("Uploading model artifacts to S3...")

        # Upload model
        self.s3.upload(
            self.config.model_path,
            self.config.s3_bucket,
            f"{self.config.s3_artifact_prefix}model.keras"
        )

        # Upload training history
        history_path = Path("artifacts/model_trainer/history.json")
        if history_path.exists():
            self.s3.upload(
                history_path,
                self.config.s3_bucket,
                f"{self.config.s3_artifact_prefix}history.json"
            )

        # Upload evaluation artifacts
        eval_files = [
            self.config.metrics_path,
            Path("artifacts/model_evaluation/results.parquet"),
            Path("artifacts/model_evaluation/confusion_matrix.png"),
            Path("artifacts/model_evaluation/pred_vs_true.png"),
            Path("artifacts/model_evaluation/error_distribution.png")
        ]

        for file in eval_files:
            if file.exists():
                self.s3.upload(
                    file,
                    self.config.s3_bucket,
                    f"{self.config.s3_artifact_prefix}{file.name}"
                )

        logging.info("All artifacts uploaded to S3 successfully")

    # RUN
    def run(self):
        logging.info("========== MODEL REGISTRY STARTED ==========")

        rmse, nasa = self.load_metrics()

        if not self.should_promote(rmse, nasa):
            logging.warning("Model promotion rejected")
            return

        version = self.register_model()
        self.promote_model(version)
        self.upload_to_s3()

        logging.info("========== MODEL REGISTRY COMPLETED ==========\n")