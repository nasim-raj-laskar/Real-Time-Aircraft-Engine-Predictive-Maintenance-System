import os
import tempfile
import matplotlib.pyplot as plt
import mlflow
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
