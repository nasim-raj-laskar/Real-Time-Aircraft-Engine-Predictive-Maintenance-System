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

    # EVALUATE
    def evaluate(self):
        model, X_test, y_test, rul_clip = self.load_artifacts()

        logging.info("Generating predictions...")

        # Model outputs normalized predictions (0-1), denormalize to (0-125)
        preds = (model.predict(X_test).flatten() * rul_clip)
        preds = np.clip(preds, 0, rul_clip)
        
        # y_test is already in actual RUL scale (0-125), NOT normalized
        y_true = y_test
        
        logging.info(f"Prediction range: {preds.min():.2f} - {preds.max():.2f}")
        logging.info(f"True RUL range: {y_true.min():.2f} - {y_true.max():.2f}")

        # COMPUTE METRICS
        rmse = compute_rmse(y_true, preds)
        nasa = compute_nasa_score(y_true, preds)

        logging.info(f"RMSE: {rmse:.2f}")
        logging.info(f"NASA Score: {nasa:.2f}")

        # Log evaluation metrics to MLflow
        mlflow.log_metrics({
            "test_rmse": rmse,
            "test_nasa_score": nasa
        })

        # RESULTS DATAFRAME
        results = pd.DataFrame({
            "true_rul": y_true,
            "pred_rul": preds,
            "error": preds - y_true,
            "abs_error": np.abs(preds - y_true)
        })

        results.to_parquet(self.config.results_path, index=False)
        logging.info(f"Results saved at: {self.config.results_path}")

        # CLASSIFICATION METRICS
        results["critical_true"] = (results["true_rul"] < 30)
        results["critical_pred"] = (results["pred_rul"] < 30)
        
        # Log distribution for debugging
        n_critical_true = results["critical_true"].sum()
        n_critical_pred = results["critical_pred"].sum()
        logging.info(f"Critical engines (true): {n_critical_true}/{len(results)}")
        logging.info(f"Critical engines (pred): {n_critical_pred}/{len(results)}")

        cls_report = compute_classification_report(
            results["critical_true"],
            results["critical_pred"]
        )
        
        logging.info(f"Classification report keys: {cls_report.keys()}")

        # Extract metrics using the target_names we defined
        critical_metrics = cls_report.get("Critical", {})
        
        precision_critical = critical_metrics.get("precision", 0)
        recall_critical = critical_metrics.get("recall", 0)
        f1_critical = critical_metrics.get("f1-score", 0)
        
        logging.info(f"Precision (Critical): {precision_critical:.3f}")
        logging.info(f"Recall (Critical): {recall_critical:.3f}")
        logging.info(f"F1-Score (Critical): {f1_critical:.3f}")

        mlflow.log_metrics({
            "precision_critical": precision_critical,
            "recall_critical": recall_critical,
            "f1_critical": f1_critical,
        })

        # SAVE METRICS
        metrics = {
            "rmse": float(rmse),
            "nasa_score": float(nasa),
            "classification_report": cls_report
        }

        save_json(self.config.metrics_path, metrics)
        logging.info(f"Metrics saved at: {self.config.metrics_path}")

        # GENERATE PLOTS
        save_confusion_matrix(
            results["critical_true"],
            results["critical_pred"],
            self.config.confusion_matrix_path
        )
        save_prediction_plot(
            y_true,
            preds,
            rul_clip,
            self.config.prediction_plot_path
        )
        save_error_distribution(
            results["error"],
            self.config.error_distribution_path
        )

        # LOG EVALUATION ARTIFACTS TO MLFLOW
        mlflow.log_artifact(str(self.config.confusion_matrix_path), artifact_path="evaluation")
        mlflow.log_artifact(str(self.config.prediction_plot_path), artifact_path="evaluation")
        mlflow.log_artifact(str(self.config.error_distribution_path), artifact_path="evaluation")
        mlflow.log_artifact(str(self.config.metrics_path), artifact_path="evaluation")
        mlflow.log_artifact(str(self.config.results_path), artifact_path="evaluation")

        logging.info("Evaluation artifacts logged to MLflow")

    # RUN
    def run(self):
        logging.info("========== MODEL EVALUATION STARTED ==========")
        self.evaluate()
        logging.info("========== MODEL EVALUATION COMPLETED ==========\n")