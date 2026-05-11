import os
import tempfile
import numpy as np
import matplotlib.pyplot as plt
import mlflow
from sklearn.metrics import confusion_matrix
from src.logging.logger import logging


def log_training_curves(history):
    logging.info("Generating training curves...")
    with tempfile.TemporaryDirectory() as tmp:

        for metric, title, ylabel in [
            ("loss", "Loss Curve", "Loss"),
            ("rmse", "RMSE Curve", "RMSE"),
        ]:
            fig, ax = plt.subplots()
            ax.plot(history[metric], label=f"train_{metric}")
            ax.plot(history[f"val_{metric}"], label=f"val_{metric}")
            ax.set_title(title)
            ax.set_xlabel("Epoch")
            ax.set_ylabel(ylabel)
            ax.legend()
            path = os.path.join(tmp, f"{metric}_curve.png")
            fig.savefig(path)
            plt.close(fig)
            mlflow.log_artifact(path, artifact_path="plots")
            logging.info(f"{metric}_curve.png logged to MLflow")

    logging.info("Training curves logging complete")


def save_confusion_matrix(y_true, y_pred, path):
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(5, 4))
    plt.imshow(cm)
    plt.title("Confusion Matrix")
    plt.colorbar()
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(j, i, cm[i, j], ha="center", va="center")
    plt.savefig(path)
    plt.close()
    logging.info("Confusion matrix saved")


def save_prediction_plot(y_true, preds, rul_clip, path):
    plt.figure(figsize=(6, 6))
    plt.scatter(y_true, preds, alpha=0.6)
    plt.plot([0, rul_clip], [0, rul_clip])
    plt.xlabel("True RUL")
    plt.ylabel("Predicted RUL")
    plt.title("Predicted vs True")
    plt.savefig(path)
    plt.close()
    logging.info("Prediction plot saved")


def save_error_distribution(errors, path):
    plt.figure(figsize=(6, 4))
    plt.hist(errors, bins=30)
    plt.xlabel("Prediction Error")
    plt.ylabel("Count")
    plt.title("Error Distribution")
    plt.savefig(path)
    plt.close()
    logging.info("Error distribution saved")
