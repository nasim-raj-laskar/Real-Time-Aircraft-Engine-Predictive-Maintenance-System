from pathlib import Path
import numpy as np
from streaming.model.engine_event import EngineEvent, SENSOR_NAMES

_DEFAULT_CSV = Path(__file__).parents[3] / "streaming" / "src" / "main" / "resources" / "scaler_params.csv"


class NormalizationFunction:
    """
    Stateless MinMax normalization applied per EngineEvent.
    Reads scaler_params.csv once at construction — no file I/O per event.
    """

    def __init__(self, scaler_params_path: Path = _DEFAULT_CSV):
        rows = Path(scaler_params_path).read_text().strip().splitlines()
        self.sensor_min = np.array([float(v) for v in rows[0].split(",")], dtype=np.float32)
        self.sensor_max = np.array([float(v) for v in rows[1].split(",")], dtype=np.float32)
        self._range = np.where(
            self.sensor_max - self.sensor_min == 0,
            1.0,
            self.sensor_max - self.sensor_min,
        )

    def normalize(self, event: EngineEvent) -> EngineEvent:
        """Normalize all sensor readings in-place, clamp to [0, 1], return event."""
        raw = np.array(event.sensor_array(), dtype=np.float32)
        normed = np.clip((raw - self.sensor_min) / self._range, 0.0, 1.0)
        for i, name in enumerate(SENSOR_NAMES):
            event.sensors[name] = float(normed[i])
        return event
