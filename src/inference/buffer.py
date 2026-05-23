import json
import os
from typing import List, Optional

import redis


class EngineBuffer:
    """Redis-backed per-engine rolling buffer.

    Uses a Redis list per engine: key template `engine:{engine_id}:buffer`.
    Stores JSON-encoded dicts. Maintains a fixed window size with LTRIM
    and an optional TTL to automatically expire stale engines.
    """

    def __init__(
        self,
        window_size: int,
        sensor_cols: List[str],
        redis_url: Optional[str] = None,
        ttl_seconds: Optional[int] = 3600,
    ):
        self.window_size = int(window_size)
        self.sensor_cols = sensor_cols
        self.ttl = int(ttl_seconds) if ttl_seconds is not None else None

        # Resolve redis connection
        url = redis_url or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
        self.client = redis.from_url(url, decode_responses=True)

        # verify connection
        try:
            self.client.ping()
        except Exception as e:
            raise RuntimeError(f"Unable to connect to Redis at {url}: {e}")

    def _key(self, engine_id: str) -> str:
        return f"engine:{engine_id}:buffer"

    def push(self, engine_id: str, reading: dict) -> None:
        """Append a single raw reading for an engine. Raises KeyError if keys missing."""
        missing = [s for s in self.sensor_cols if s not in reading]
        if missing:
            raise KeyError(f"Missing keys: {missing}")

        key = self._key(engine_id)
        payload = json.dumps(reading)
        pipe = self.client.pipeline()
        # append at right (oldest at index 0)
        pipe.rpush(key, payload)
        # keep only the last `window_size` elements
        pipe.ltrim(key, -self.window_size, -1)
        if self.ttl:
            pipe.expire(key, self.ttl)
        pipe.execute()

    def get_window(self, engine_id: str) -> List[dict]:
        key = self._key(engine_id)
        arr = self.client.lrange(key, 0, -1)
        if len(arr) < self.window_size:
            raise ValueError(f"Not enough readings for engine {engine_id}: {len(arr)}/{self.window_size}")
        # arr is oldest->newest
        window = [json.loads(x) for x in arr[-self.window_size :]]
        return window

    def size(self, engine_id: str) -> int:
        key = self._key(engine_id)
        return int(self.client.llen(key))

    def list_engines(self) -> List[str]:
        """Return all engine IDs that currently have a buffer key in Redis."""
        return [
            k.split(":")[1]
            for k in self.client.keys("engine:*:buffer")
        ]


class InMemoryEngineBuffer:
    """Simple thread-safe in-memory buffer used as a fallback when Redis is unavailable."""

    def __init__(self, window_size: int, sensor_cols: List[str]):
        from collections import defaultdict, deque
        import threading

        self.window_size = int(window_size)
        self.sensor_cols = sensor_cols
        self.buffers = defaultdict(lambda: deque(maxlen=self.window_size))
        self.lock = threading.Lock()

    def push(self, engine_id: str, reading: dict) -> None:
        missing = [s for s in self.sensor_cols if s not in reading]
        if missing:
            raise KeyError(f"Missing keys: {missing}")
        with self.lock:
            self.buffers[engine_id].append(reading.copy())

    def get_window(self, engine_id: str) -> List[dict]:
        with self.lock:
            buf = list(self.buffers.get(engine_id, []))
            if len(buf) < self.window_size:
                raise ValueError(f"Not enough readings for engine {engine_id}: {len(buf)}/{self.window_size}")
            return buf[-self.window_size :]

    def size(self, engine_id: str) -> int:
        with self.lock:
            return len(self.buffers.get(engine_id, []))

    def list_engines(self) -> List[str]:
        with self.lock:
            return list(self.buffers.keys())
