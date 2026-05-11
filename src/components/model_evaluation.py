import json
import boto3
import numpy as np
import pandas as pd
import tensorflow as tf
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import (mean_squared_error,confusion_matrix,classification_report)
from src.entity.config_entity import ModelEvaluationConfig
from src.logging.logger import logging
from src.utils.common import save_json


class ModelEvaluation:
    def __init__(self, config: ModelEvaluationConfig):
        self.config = config
        self.s3 = boto3.client("s3")

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
            output_dict=True
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

        #  CONFUSION MATRIX 
        cm = confusion_matrix(
            results["critical_true"],
            results["critical_pred"]
        )

        plt.figure(figsize=(5, 4))

        plt.imshow(cm)

        plt.title("Confusion Matrix")

        plt.colorbar()

        plt.xlabel("Predicted")
        plt.ylabel("Actual")

        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):

                plt.text(
                    j,
                    i,
                    cm[i, j],
                    ha="center",
                    va="center"
                )

        plt.savefig(
            self.config.confusion_matrix_path
        )

        plt.close()

        logging.info("Confusion matrix saved")

        #  PRED VS TRUE 
        plt.figure(figsize=(6, 6))

        plt.scatter(
            y_true,
            preds,
            alpha=0.6
        )

        plt.plot(
            [0, rul_clip],
            [0, rul_clip]
        )

        plt.xlabel("True RUL")
        plt.ylabel("Predicted RUL")

        plt.title("Predicted vs True")

        plt.savefig(
            self.config.prediction_plot_path
        )

        plt.close()

        logging.info("Prediction plot saved")

        #  ERROR DISTRIBUTION 
        plt.figure(figsize=(6, 4))

        plt.hist(
            results["error"],
            bins=30
        )

        plt.xlabel("Prediction Error")
        plt.ylabel("Count")

        plt.title("Error Distribution")

        plt.savefig(
            self.config.error_distribution_path
        )

        plt.close()

        logging.info("Error distribution saved")

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

            self.s3.upload_file(

                str(file),

                self.config.s3_bucket,

                f"{self.config.s3_artifact_prefix}{file.name}"
            )

            logging.info(f"Uploaded: {file.name}")

    #  RUN 
    def run(self):

        logging.info(
            "========== MODEL EVALUATION STARTED =========="
        )

        self.evaluate()

        logging.info(
            "========== MODEL EVALUATION COMPLETED ==========\n"
        )