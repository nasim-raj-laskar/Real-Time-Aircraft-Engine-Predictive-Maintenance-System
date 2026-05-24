import os
import redis
from streaming.model.feature_vector import FeatureVector

TTL_SECONDS = 3600


class RedisSink:
    """
    Writes FeatureVectors to Redis as big-endian float32 byte arrays.

    Key schema (matches src/inference/feature_store.py):
        engine:{id}:features  → bytes  (window_size × n_sensors × 4 bytes)
        engine:{id}:meta      → hash   { engine_id, cycle, event_time, window_size, n_sensors }
    """

    def __init__(self, redis_url: str = None):
        url = redis_url or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
        self._pool = redis.ConnectionPool.from_url(url, max_connections=32, decode_responses=False)

    @property
    def _client(self) -> redis.Redis:
        return redis.Redis(connection_pool=self._pool)

    def write(self, fv: FeatureVector) -> None:
        r = self._client
        pipe = r.pipeline(transaction=False)

        pipe.set(fv.redis_feature_key, fv.to_bytes())
        pipe.expire(fv.redis_feature_key, TTL_SECONDS)

        pipe.hset(fv.redis_meta_key, mapping={
            "engine_id":   fv.engine_id,
            "cycle":       str(fv.cycle),
            "event_time":  str(fv.event_time),
            "window_size": str(fv.window_size),
            "n_sensors":   str(fv.n_sensors),
        })
        pipe.expire(fv.redis_meta_key, TTL_SECONDS)

        pipe.execute()

    def close(self) -> None:
        self._pool.disconnect()
