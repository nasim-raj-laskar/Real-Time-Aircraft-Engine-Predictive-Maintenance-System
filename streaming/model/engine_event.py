from dataclasses import dataclass, field
from typing import Dict
import json

SENSOR_NAMES = ["s2", "s3", "s4", "s7", "s9", "s11", "s12", "s14", "s17", "s20", "s21"]

# Column indices in the raw FD001 text file (0-indexed)
SENSOR_INDICES = [6, 7, 8, 11, 13, 15, 16, 18, 21, 24, 25]


@dataclass
class EngineEvent:
    engine_id: str
    cycle: int
    event_time_ms: int
    sensors: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: bytes) -> "EngineEvent":
        data = json.loads(raw)
        return cls(
            engine_id=data["engine_id"],
            cycle=data["cycle"],
            event_time_ms=data["event_time_ms"],
            sensors=data["sensors"],
        )

    def to_json(self) -> str:
        return json.dumps({
            "engine_id": self.engine_id,
            "cycle": self.cycle,
            "event_time_ms": self.event_time_ms,
            "sensors": self.sensors,
        })

    def sensor_array(self) -> list:
        return [self.sensors.get(s, 0.0) for s in SENSOR_NAMES]
