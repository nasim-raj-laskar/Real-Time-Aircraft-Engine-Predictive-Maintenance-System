import json
import mlflow
import numpy as np
import pandas as pd
import tensorflow as tf
from mlflow.models.signature import infer_signature
from pathlib import Path
from src.entity.config_entity import ModelEvaluationConfig
from src.logging.logger import logging
from src.utils.common import save_json
from src.metrics.plot import save_confusion_matrix, save_prediction_plot, save_error_distribution
from src.metrics.scores import compute_rmse, compute_nasa_score, compute_classification_report
from src.cloud.s3 import S3Client
from src.utils.mlflow_setup import setup_mlflow


class ModelEvaluation:
    def __init__(self, config: ModelEvaluationConfig):
        self.config = config
        self.s3 = S3Client()

    #LOAD
    def load_artifacts(self):
        logging.info("Loading evaluation artifacts...")
        model = tf.keras.models.load_model(self.config.model_path)
        X_test = np.load(self.config.gold_dir / "X_test.npy")
        y_test = np.load(self.config.gold_dir / "y_test.npy")
        with open(self.config.gold_dir / "feature_config.json") as f:
            feature_config = json.load(f)
        rul_clip = feature_config["rul_clip"]
        logging.info(f"X_test shape: {X_test.shape}")

        return model, X_test, y_test, rul_clip

    #  EVALUATE 
    def evaluate(self):
        model, X_test, y_test, rul_clip = (self.load_artifacts())

        logging.info("Generating predictions...")

        preds = (model.predict(X_test).flatten()* rul_clip)

        preds = np.clip(preds,0,rul_clip)

        y_true = np.clip(y_test * rul_clip,0,rul_clip)

        #  METRICS 
        rmse = compute_rmse(y_true, preds)
        nasa = compute_nasa_score(y_true, preds)

        logging.info(f"RMSE: {rmse:.2f}")
        logging.info(f"NASA Score: {nasa:.2f}")

        mlflow.log_metrics({"rmse": rmse, "nasa_score": nasa})

        #  RESULTS DF 
        results = pd.DataFrame({
            "true_rul": y_true,
            "pred_rul": preds,
            "error": preds - y_true,
            "abs_error": np.abs(preds - y_true)})

        results.to_parquet(self.config.results_path,index=False)

        logging.info(f"Results saved at: {self.config.results_path}")

        #  CLASSIFICATION 
        results["critical_true"] = (results["true_rul"] < 30)

        results["critical_pred"] = (results["pred_rul"] < 30)

        cls_report = compute_classification_report(results["critical_true"], results["critical_pred"])

        mlflow.log_metrics({
            "precision_critical": cls_report.get("True", {}).get("precision", 0),
            "recall_critical":    cls_report.get("True", {}).get("recall", 0),
            "f1_critical":        cls_report.get("True", {}).get("f1-score", 0),
        })

        #  SAVE METRICS 
        metrics = {
            "rmse": float(rmse),
            "nasa_score": float(nasa),
            "classification_report": cls_report}

        save_json(self.config.metrics_path,metrics)

        logging.info(f"Metrics saved at: {self.config.metrics_path}")

        #PLOTS 
        save_confusion_matrix(results["critical_true"], results["critical_pred"], self.config.confusion_matrix_path)
        save_prediction_plot(y_true, preds, rul_clip, self.config.prediction_plot_path)
        save_error_distribution(results["error"], self.config.error_distribution_path)

        mlflow.log_artifact(str(self.config.confusion_matrix_path), artifact_path="evaluation/plots")
        mlflow.log_artifact(str(self.config.prediction_plot_path), artifact_path="evaluation/plots")
        mlflow.log_artifact(str(self.config.error_distribution_path), artifact_path="evaluation/plots")
        mlflow.log_artifact(str(self.config.metrics_path), artifact_path="evaluation")
        mlflow.log_artifact(str(self.config.results_path), artifact_path="evaluation")
        signature = infer_signature(X_test, preds)
        mlflow.tensorflow.log_model(model, name="model", signature=signature)

        logging.info("Artifacts and model logged to MLflow")

        #  UPLOAD TO S3 
        logging.info("Uploading evaluation artifacts to S3...")

        files = [
            self.config.metrics_path,
            self.config.results_path,
            self.config.confusion_matrix_path,
            self.config.prediction_plot_path,
            self.config.error_distribution_path
        ]

        for file in files:
            self.s3.upload(file, self.config.s3_bucket, f"{self.config.s3_artifact_prefix}{file.name}")

    #  RUN 
    def run(self):
        logging.info("========== MODEL EVALUATION STARTED ==========")
        setup_mlflow()
        with mlflow.start_run(run_name="model-evaluation"):
            self.evaluate()
        logging.info("========== MODEL EVALUATION COMPLETED ==========\n")