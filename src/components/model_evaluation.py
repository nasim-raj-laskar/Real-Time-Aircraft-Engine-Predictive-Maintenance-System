import json
import numpy as np
import pandas as pd
import tensorflow as tf
from pathlib import Path
from sklearn.metrics import mean_squared_error, classification_report
from src.entity.config_entity import ModelEvaluationConfig
from src.logging.logger import logging
from src.utils.common import save_json
from src.metrics.plot import save_confusion_matrix, save_prediction_plot, save_error_distribution
from src.cloud.s3 import S3Client


class ModelEvaluation:
    def __init__(self, config: ModelEvaluationConfig):
        self.config = config
        self.s3 = S3Client()

    #NASA SCORE 
    def nasa_score(self, y_true, y_pred):

        d = y_pred.flatten() - y_true.flatten()

        return float(
            np.sum(
                np.where(
                    d < 0,
                    np.exp(-d / 13) - 1,
                    np.exp(d / 10) - 1
                )
            )
        )

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

        y_true = np.clip(
            y_test * rul_clip,
            0,
            rul_clip
        )

        #  METRICS 
        rmse = np.sqrt(mean_squared_error(y_true, preds))

        nasa = self.nasa_score(y_true,preds)

        logging.info(f"RMSE: {rmse:.2f}")
        logging.info(f"NASA Score: {nasa:.2f}")

        #  RESULTS DF 
        results = pd.DataFrame({

            "true_rul": y_true,
            "pred_rul": preds,

            "error": preds - y_true,

            "abs_error": np.abs(
                preds - y_true
            )
        })

        results.to_parquet(
            self.config.results_path,
            index=False
        )

        logging.info(
            f"Results saved at: {self.config.results_path}"
        )

        #  CLASSIFICATION 
        results["critical_true"] = (
            results["true_rul"] < 30
        )

        results["critical_pred"] = (
            results["pred_rul"] < 30
        )

        cls_report = classification_report(
            results["critical_true"],
            results["critical_pred"],
            output_dict=True,
            zero_division=0
        )

        #  SAVE METRICS 
        metrics = {

            "rmse": float(rmse),

            "nasa_score": float(nasa),

            "classification_report": cls_report
        }

        save_json(
            self.config.metrics_path,
            metrics
        )

        logging.info(
            f"Metrics saved at: {self.config.metrics_path}"
        )

        #  PLOTS 
        save_confusion_matrix(results["critical_true"], results["critical_pred"], self.config.confusion_matrix_path)
        save_prediction_plot(y_true, preds, rul_clip, self.config.prediction_plot_path)
        save_error_distribution(results["error"], self.config.error_distribution_path)

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

        logging.info(
            "========== MODEL EVALUATION STARTED =========="
        )

        self.evaluate()

        logging.info(
            "========== MODEL EVALUATION COMPLETED ==========\n"
        )