from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from streaming.model.engine_event import EngineEvent, SENSOR_NAMES
from streaming.model.feature_vector import FeatureVector


@dataclass
class _EngineState:
    window: deque = field(default_factory=deque)
    last_cycle: int = -1


class RollingWindowFunction:
    """
    Maintains per-engine rolling buffers and emits FeatureVectors.

    Emits a FeatureVector only when the buffer holds exactly window_size
    normalized sensor rows. Drops duplicate and out-of-order cycles.

    In PyFlink this is wrapped as a KeyedProcessFunction backed by
    managed ListState. In standalone mode it is used directly.
    """

    def __init__(
        self,
        window_size: int = 30,
        on_feature: Optional[Callable[[FeatureVector], None]] = None,
    ):
        self.window_size = window_size
        self.on_feature = on_feature
        self._states: dict[str, _EngineState] = {}

    def process(self, event: EngineEvent) -> Optional[FeatureVector]:
        """
        Process one normalized EngineEvent.
        Returns a FeatureVector when the buffer is full, else None.
        """
        state = self._states.setdefault(event.engine_id, _EngineState())

        # Drop duplicates and late arrivals
        if event.cycle <= state.last_cycle:
            return None
        state.last_cycle = event.cycle

        state.window.append(event.sensor_array())
        if len(state.window) > self.window_size:
            state.window.popleft()

        if len(state.window) < self.window_size:
            return None

        flat = [v for row in state.window for v in row]
        fv = FeatureVector(
            engine_id=event.engine_id,
            cycle=event.cycle,
            event_time=event.event_time_ms,
            features=flat,
            window_size=self.window_size,
            n_sensors=len(SENSOR_NAMES),
        )
        if self.on_feature:
            self.on_feature(fv)
        return fv

    def buffer_size(self, engine_id: str) -> int:
        return len(self._states[engine_id].window) if engine_id in self._states else 0

    def active_engines(self) -> list:
        return list(self._states.keys())
