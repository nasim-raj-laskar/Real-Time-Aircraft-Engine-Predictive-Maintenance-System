import numpy as np
from fastapi import HTTPException


class InferencePreprocessor:
    def __init__(self, scaler, sensor_cols: list, window_size: int = 30):
        self.scaler = scaler
        self.sensor_cols = sensor_cols
        self.window_size = window_size

    def preprocess(self, raw_reading: dict) -> np.ndarray:
        """Convert a single raw sensor reading dict to a normalized (n_features,) array."""
        missing = [s for s in self.sensor_cols if s not in raw_reading]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required sensor keys: {missing}"
            )

        try:
            values = np.array(
                [raw_reading[s] for s in self.sensor_cols],
                dtype=np.float32
            ).reshape(1, -1)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid raw sensor values: {exc}"
            )

        try:
            normalized = self.scaler.transform(values)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to normalize raw sensor values: {exc}"
            )

        return normalized.flatten()

    def build_sequence(self, readings: list) -> np.ndarray:
        """Convert a list of raw sensor reading dicts to a model-ready (1, window_size, n_features) array."""
        if len(readings) != self.window_size:
            raise HTTPException(
                status_code=400,
                detail=f"Expected {self.window_size} readings, got {len(readings)}"
            )

        sequence = np.stack([self.preprocess(r) for r in readings])
        return sequence.reshape(1, self.window_size, len(self.sensor_cols))
