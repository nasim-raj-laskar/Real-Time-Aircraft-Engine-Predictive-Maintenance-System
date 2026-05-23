import os
import struct
from typing import Optional

import numpy as np
import redis


class RedisFeatureStore:
    """Reads and writes inference-ready feature tensors from Redis.

    Key schema (matches the Flink RedisSink in doc/06):
        engine:{engine_id}:features  →  bytes  (window_size × n_sensors float32, big-endian)
        engine:{engine_id}:meta      →  hash   { engine_id, cycle, event_time, window_size, n_sensors }

    The feature_store is the bridge between the streaming pipeline (Flink writes)
    and the inference service (FastAPI reads). It is read-only from the API side;
    writes are used only by the Flink RedisSink or the /push buffer pathway.
    """

    def __init__(
        self,
        window_size: int,
        n_sensors: int,
        redis_url: Optional[str] = None,
        ttl_seconds: int = 3600,
    ):
        self.window_size = window_size
        self.n_sensors = n_sensors
        self.ttl = ttl_seconds
        self._n_floats = window_size * n_sensors

        url = redis_url or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
        self.client = redis.from_url(url, decode_responses=False)

        try:
            self.client.ping()
        except Exception as e:
            raise RuntimeError(f"RedisFeatureStore: cannot connect to Redis at {url}: {e}")

    # ── key helpers ──────────────────────────────────────────────────────────

    def _feat_key(self, engine_id: str) -> bytes:
        return f"engine:{engine_id}:features".encode()

    def _meta_key(self, engine_id: str) -> bytes:
        return f"engine:{engine_id}:meta".encode()

    # ── write (used by /push pathway and tests) ──────────────────────────────

    def set_features(self, engine_id: str, window: np.ndarray, meta: dict = None) -> None:
        """Store a (window_size, n_sensors) float32 array and optional metadata."""
        if window.shape != (self.window_size, self.n_sensors):
            raise ValueError(
                f"Expected shape ({self.window_size}, {self.n_sensors}), got {window.shape}"
            )
        raw = struct.pack(f">{self._n_floats}f", *window.flatten().tolist())
        pipe = self.client.pipeline()
        pipe.set(self._feat_key(engine_id), raw)
        pipe.expire(self._feat_key(engine_id), self.ttl)
        if meta:
            str_meta = {k.encode(): str(v).encode() for k, v in meta.items()}
            pipe.hset(self._meta_key(engine_id), mapping=str_meta)
            pipe.expire(self._meta_key(engine_id), self.ttl)
        pipe.execute()

    # ── read ─────────────────────────────────────────────────────────────────

    def get_features(self, engine_id: str) -> Optional[np.ndarray]:
        """Return the latest (window_size, n_sensors) float32 array, or None if missing."""
        raw = self.client.get(self._feat_key(engine_id))
        if raw is None:
            return None
        expected_bytes = self._n_floats * 4
        if len(raw) != expected_bytes:
            return None
        values = struct.unpack(f">{self._n_floats}f", raw)
        return np.array(values, dtype=np.float32).reshape(self.window_size, self.n_sensors)

    def get_meta(self, engine_id: str) -> Optional[dict]:
        """Return metadata hash for an engine, or None if missing."""
        raw = self.client.hgetall(self._meta_key(engine_id))
        if not raw:
            return None
        return {k.decode(): v.decode() for k, v in raw.items()}

    def list_active_engines(self) -> list[str]:
        """Return all engine IDs that currently have a feature tensor in Redis."""
        return [
            k.decode().split(":")[1]
            for k in self.client.keys(b"engine:*:features")
        ]

    def exists(self, engine_id: str) -> bool:
        return bool(self.client.exists(self._feat_key(engine_id)))
