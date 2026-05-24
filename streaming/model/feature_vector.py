from dataclasses import dataclass
import struct
import numpy as np


@dataclass
class FeatureVector:
    engine_id: str
    cycle: int
    event_time: int
    features: list        # flattened (window_size * n_sensors,) float list
    window_size: int
    n_sensors: int

    def to_numpy(self) -> np.ndarray:
        return np.array(self.features, dtype=np.float32).reshape(self.window_size, self.n_sensors)

    def to_bytes(self) -> bytes:
        """Serialize as big-endian IEEE 754 float32 — matches struct.unpack in inference service."""
        return struct.pack(f">{len(self.features)}f", *self.features)

    @property
    def redis_feature_key(self) -> str:
        return f"engine:{self.engine_id}:features"

    @property
    def redis_meta_key(self) -> str:
        return f"engine:{self.engine_id}:meta"
