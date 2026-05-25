"""
PyFlink entry point for the Aircraft Telemetry Feature Pipeline.

Two source modes (auto-detected via env vars):
  - Solace PubSub+  : set SOLACE_HOST — uses the Solace Flink connector JAR
  - Redis Streams   : default (no broker needed) — reads from telemetry:stream

Run (Flink cluster):
    flink run -py streaming/pipeline/telemetry_pipeline.py \\
              --parallelism 8 \\
              -pyfs streaming/ \\
              -j  /opt/flink/lib/flink-connector-solace-1.1.0.jar

Run (local mini-cluster, no Flink install needed):
    python -m streaming.pipeline.telemetry_pipeline
"""

import json
import os
import time
from pathlib import Path

from pyflink.datastream import StreamExecutionEnvironment, CheckpointingMode
from pyflink.datastream.functions import MapFunction, KeyedProcessFunction, SinkFunction, RuntimeContext
from pyflink.datastream.state import ListStateDescriptor, ValueStateDescriptor
from pyflink.common import WatermarkStrategy, Duration
from pyflink.common.typeinfo import Types

from streaming.model.engine_event import EngineEvent, SENSOR_NAMES
from streaming.model.feature_vector import FeatureVector
from streaming.pipeline.functions.normalization import NormalizationFunction
from streaming.pipeline.functions.rolling_window import RollingWindowFunction
from streaming.pipeline.sinks.redis_sink import RedisSink
from streaming.pipeline.sinks.s3_parquet_sink import S3ParquetSink
from streaming.producer.telemetry_producer import REDIS_STREAM_KEY

_SCALER_CSV = Path(__file__).parents[1] / "src" / "main" / "resources" / "scaler_params.csv"
_WINDOW_SIZE = 30
_FLUSH_EVERY = int(os.getenv("FLUSH_EVERY", "500"))


# ── Stage 1: Normalization (stateless MapFunction) ────────────────────────────

class NormalizeMap(MapFunction):
    """Wraps NormalizationFunction as a Flink MapFunction.
    Loaded once per TaskManager slot via open(), not per event.
    """

    def open(self, runtime_context: RuntimeContext):
        self._fn = NormalizationFunction(_SCALER_CSV)

    def map(self, raw: bytes) -> EngineEvent:
        event = EngineEvent.from_json(raw)
        return self._fn.normalize(event)


# ── Stage 2: Rolling Window (stateful KeyedProcessFunction) ──────────────────

class RollingWindowProcess(KeyedProcessFunction):
    """Per-engine keyed state backed by Flink managed ListState (RocksDB in prod).

    State survives job failures and is restored from checkpoints automatically.
    Emits a FeatureVector only when the buffer holds exactly window_size rows.
    """

    def open(self, runtime_context: RuntimeContext):
        buffer_desc = ListStateDescriptor("cycle-buffer", Types.PICKLED_BYTE_ARRAY())
        self._buffer = runtime_context.get_list_state(buffer_desc)

        last_cycle_desc = ValueStateDescriptor("last-cycle", Types.INT())
        self._last_cycle = runtime_context.get_state(last_cycle_desc)

    def process_element(self, event: EngineEvent, ctx, out):
        last = self._last_cycle.value()

        # Reset on producer loop-back (cycle resets to 1)
        if event.cycle == 1:
            self._last_cycle.update(-1)
            self._buffer.clear()
            last = -1

        # Drop duplicates and out-of-order events (at-least-once re-delivery guard)
        if last is not None and event.cycle <= last:
            return
        self._last_cycle.update(event.cycle)

        self._buffer.add(event.sensor_array())

        rows = list(self._buffer.get())
        if len(rows) > _WINDOW_SIZE:
            rows = rows[-_WINDOW_SIZE:]
            self._buffer.clear()
            for row in rows:
                self._buffer.add(row)

        if len(rows) < _WINDOW_SIZE:
            return

        flat = [v for row in rows for v in row]
        out.collect(FeatureVector(
            engine_id=event.engine_id,
            cycle=event.cycle,
            event_time=event.event_time_ms,
            features=flat,
            window_size=_WINDOW_SIZE,
            n_sensors=len(SENSOR_NAMES),
        ))


# ── Sink 1: Redis online feature store ───────────────────────────────────────

class RedisSinkFunction(SinkFunction):
    """Writes each FeatureVector to Redis. One connection pool per TaskManager."""

    def open(self, runtime_context: RuntimeContext):
        self._sink = RedisSink(redis_url=os.getenv("REDIS_URL"))

    def invoke(self, fv: FeatureVector, context):
        self._sink.write(fv)

    def close(self):
        self._sink.close()


# ── Sink 2: S3 Parquet offline store (checkpoint-aligned flush) ───────────────

class S3CheckpointSink(SinkFunction):
    """Buffers FeatureVectors and flushes to S3 Parquet on finish() (per checkpoint)."""

    def open(self, runtime_context: RuntimeContext):
        self._sink = S3ParquetSink()
        self._count = 0

    def invoke(self, fv: FeatureVector, context):
        self._sink.add(fv)
        self._count += 1
        if self._count % _FLUSH_EVERY == 0:
            n = self._sink.flush()
            print(f"[s3-sink] Flushed {n} records to Parquet")

    def close(self):
        self._sink.close()


# ── Redis Streams source (default, no broker needed) ─────────────────────────

class RedisStreamSourceFunction(MapFunction):
    """Reads raw event bytes from a Redis Stream (XREAD).

    Used as a polling source when SOLACE_HOST is not set.
    Wraps the same Redis stream that the standalone producer writes to.
    """

    def open(self, runtime_context: RuntimeContext):
        import redis
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._rc = redis.from_url(url, decode_responses=False)
        self._last_id = "0"

    def map(self, value):
        # passthrough — actual reading is done in the source iterator
        return value


def _build_redis_stream_source(env: StreamExecutionEnvironment):
    """Creates a Flink source from Redis Streams via a Python iterator source."""
    import redis

    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    rc = redis.from_url(url, decode_responses=False)
    last_id = ["0"]  # mutable reference for closure

    def _event_iter():
        while True:
            try:
                results = rc.xread({REDIS_STREAM_KEY: last_id[0]}, count=200, block=1000)
                if not results:
                    continue
                messages = results[0][1]
                last_id[0] = messages[-1][0]
                if isinstance(last_id[0], bytes):
                    last_id[0] = last_id[0].decode()
                for _, fields in messages:
                    yield fields[b"data"]
            except Exception as e:
                print(f"[source] Redis read error: {e}")
                time.sleep(1)

    return env.from_collection(_event_iter(), type_info=Types.PICKLED_BYTE_ARRAY())


# ── Solace source (optional, requires JAR on classpath) ──────────────────────

def _build_solace_source(env: StreamExecutionEnvironment):
    """Builds the Solace source via PyFlink's JVM bridge.

    Requires flink-connector-solace JAR added via:
        env.add_jars("file:///opt/flink/lib/flink-connector-solace-1.1.0.jar")
    """
    from pyflink.java_gateway import get_gateway
    gw = get_gateway()
    jvm = gw.jvm

    props = jvm.com.solacesystems.jcsmp.JCSMPProperties()
    props.setProperty("HOST",     os.getenv("SOLACE_HOST",     "tcp://localhost:55555"))
    props.setProperty("VPN_NAME", os.getenv("SOLACE_VPN",      "default"))
    props.setProperty("USERNAME", os.getenv("SOLACE_USERNAME",  "admin"))
    props.setProperty("PASSWORD", os.getenv("SOLACE_PASSWORD",  "admin"))

    return (
        jvm.com.solace.connector.flink.SolaceSource.builder()
        .setSessionProperties(props)
        .setQueueName(os.getenv("SOLACE_QUEUE_NAME", "flink.feature.processor"))
        .setAckMode(
            jvm.com.solace.connector.flink.SolaceSourceConfiguration.AckMode.ON_CHECKPOINT
        )
        .build()
    )


# ── Pipeline builder ──────────────────────────────────────────────────────────

def build_pipeline(local: bool = False) -> None:
    env = StreamExecutionEnvironment.get_execution_environment()

    # Checkpointing — every 30s, exactly-once
    env.enable_checkpointing(30_000)
    env.get_checkpoint_config().set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)
    env.get_checkpoint_config().set_min_pause_between_checkpoints(10_000)
    env.get_checkpoint_config().set_tolerable_checkpoint_failure_number(2)

    # RocksDB state backend for production (heap is fine for local dev)
    if not local:
        checkpoint_dir = os.getenv(
            "FLINK_CHECKPOINT_DIR",
            "s3://aircraft-engine-data/flink-checkpoints/"
        )
        try:
            from pyflink.datastream.state_backend import RocksDBStateBackend
            env.set_state_backend(RocksDBStateBackend(checkpoint_dir, incremental_checkpoints=True))
        except Exception as e:
            print(f"[pipeline] RocksDB backend unavailable, using heap: {e}")

    parallelism = int(os.getenv("FLINK_PARALLELISM", "4" if not local else "1"))
    env.set_parallelism(parallelism)

    # ── Source ────────────────────────────────────────────────────────────────
    solace_host = os.getenv("SOLACE_HOST")
    if solace_host:
        print(f"[pipeline] Using Solace source at {solace_host}")
        solace_jar = os.getenv(
            "SOLACE_CONNECTOR_JAR",
            "/opt/flink/lib/flink-connector-solace-1.1.0.jar"
        )
        env.add_jars(f"file://{solace_jar}")
        raw_stream = (
            env.from_source(
                _build_solace_source(env),
                WatermarkStrategy
                    .for_bounded_out_of_orderness(Duration.of_seconds(5))
                    .with_idleness(Duration.of_seconds(60)),
                "Solace Telemetry Source",
            )
            .name("solace-source")
        )
    else:
        print("[pipeline] SOLACE_HOST not set — using Redis Streams source")
        raw_stream = _build_redis_stream_source(env).name("redis-stream-source")

    # ── Stage 1: Normalize (stateless) ───────────────────────────────────────
    normalized = (
        raw_stream
        .map(NormalizeMap(), output_type=Types.PICKLED_BYTE_ARRAY())
        .name("minmax-normalization")
    )

    # ── Stage 2: Rolling window (stateful, keyed by engine_id) ───────────────
    features = (
        normalized
        .key_by(lambda e: e.engine_id, key_type=Types.STRING())
        .process(RollingWindowProcess(), output_type=Types.PICKLED_BYTE_ARRAY())
        .name("rolling-window-feature-builder")
    )

    # ── Sink 1: Redis online feature store ────────────────────────────────────
    features.add_sink(RedisSinkFunction()).name("redis-online-feature-sink")

    # ── Sink 2: S3 Parquet offline store ─────────────────────────────────────
    use_s3 = os.getenv("ENABLE_S3_SINK", "false").lower() == "true"
    if use_s3:
        features.add_sink(S3CheckpointSink()).name("s3-parquet-offline-sink")
    else:
        print("[pipeline] S3 sink disabled (set ENABLE_S3_SINK=true to enable)")

    env.execute("Aircraft Telemetry Feature Pipeline")


if __name__ == "__main__":
    import argparse
    import dotenv

    dotenv.load_dotenv(
        Path(__file__).parents[1] / "config" / "solace.env",
        override=False,
    )

    parser = argparse.ArgumentParser(description="Aircraft Telemetry PyFlink Pipeline")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Run in local mini-cluster mode (no RocksDB, parallelism=1)",
    )
    args = parser.parse_args()

    build_pipeline(local=args.local)
