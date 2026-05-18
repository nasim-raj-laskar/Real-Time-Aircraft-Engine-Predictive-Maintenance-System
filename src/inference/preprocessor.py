import numpy as np
import joblib
from pathlib import Path


SENSOR_COLS = ["s2", "s3", "s4", "s7", "s9", "s11", "s12", "s14", "s17", "s20", "s21"]


class InferencePreprocessor:
    def __init__(self, scaler_path: str = "artifacts/data_transformation/scaler.pkl"):
        self.scaler = joblib.load(scaler_path)

    def preprocess(self, raw_reading: dict) -> np.ndarray:
        """
        Convert a single raw sensor reading dict to a normalized (11,) array.

        Args:
            raw_reading: dict with keys matching SENSOR_COLS (s2, s3, ..., s21)

        Returns:
            np.ndarray of shape (11,)
        """
        values = np.array([raw_reading[s] for s in SENSOR_COLS], dtype=np.float32).reshape(1, -1)
        return self.scaler.transform(values).flatten()

    def build_sequence(self, readings: list) -> np.ndarray:
        """
        Convert a list of 30 raw sensor reading dicts to a model-ready (1, 30, 11) array.

        Args:
            readings: list of 30 dicts, each with raw sensor values

        Returns:
            np.ndarray of shape (1, 30, 11)
        """
        if len(readings) != 30:
            raise ValueError(f"Expected 30 readings, got {len(readings)}")
        sequence = np.stack([self.preprocess(r) for r in readings])  # (30, 11)
        return sequence.reshape(1, 30, 11)
