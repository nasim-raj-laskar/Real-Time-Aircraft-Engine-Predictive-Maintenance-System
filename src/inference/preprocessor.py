import numpy as np
import joblib


class InferencePreprocessor:
    def __init__(self, scaler, sensor_cols: list):
        self.scaler = scaler
        self.sensor_cols = sensor_cols

    def preprocess(self, raw_reading: dict) -> np.ndarray:
        """Convert a single raw sensor reading dict to a normalized (n_features,) array."""
        values = np.array([raw_reading[s] for s in self.sensor_cols], dtype=np.float32).reshape(1, -1)
        return self.scaler.transform(values).flatten()

    def build_sequence(self, readings: list) -> np.ndarray:
        """Convert a list of 30 raw sensor reading dicts to a model-ready (1, 30, n_features) array."""
        if len(readings) != 30:
            raise ValueError(f"Expected 30 readings, got {len(readings)}")
        sequence = np.stack([self.preprocess(r) for r in readings])
        return sequence.reshape(1, 30, len(self.sensor_cols))
