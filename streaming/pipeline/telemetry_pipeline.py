"""
PyFlink entry point for the Aircraft Telemetry Feature Pipeline.

Two source modes (auto-detected via env vars):
  - Solace PubSub+  : set SOLACE_HOST — uses solace-pubsubplus Python SDK (no JAR needed)
  - Redis Streams   : default (no broker needed) — reads from telemetry:stream

Run (Flink cluster):
    flink run -py streaming/pipeline/telemetry_pipeline.py \\
              --parallelism 4 \\
              -pyfs streaming/

Run (local mini-cluster, no Flink install needed):
    python -m streaming.pipeline.telemetry_pipeline
"""

import os
import time
from pathlib import Path

from pyflink.datastream import StreamExecutionEnvironment, CheckpointingMode
from pyflink.datastream.functions import MapFunction, KeyedProcessFunction, RuntimeContext
from pyflink.datastream.state import ListStateDescriptor, ValueStateDescriptor
from pyflink.common.typeinfo import Types

from streaming.model.engine_event import EngineEvent, SENSOR_NAMES
from streaming.model.feature_vector import FeatureVector
from streaming.pipeline.functions.normalization import NormalizationFunction
from streaming.pipeline.sinks.redis_sink import RedisSink
from streaming.pipeline.sinks.s3_parquet_sink import S3ParquetSink
from streaming.producer.telemetry_producer import REDIS_STREAM_KEY

_SCALER_CSV = Path(__file__).parents[1] / "src" / "main" / "resources" / "scaler_params.csv"
_WINDOW_SIZE = 30
_FLUSH_EVERY = int(os.getenv("FLUSH_EVERY", "500"))


# -- Stage 1: Normalization (stateless MapFunction) ---------------------------

class NormalizeMap(MapFunction):
    """Wraps NormalizationFunction as a Flink MapFunction.
    Loaded once per TaskManager slot via open(), not per event.
    """

    def open(self, runtime_context: RuntimeContext):
        self._fn = NormalizationFunction(_SCALER_CSV)

    def map(self, raw: bytes) -> EngineEvent:
        event = EngineEvent.from_json(raw)
        return self._fn.normalize(event)


# -- Stage 2: Rolling Window (stateful KeyedProcessFunction) ------------------

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

        # Drop duplicates and out-of-order events (at-least-once re-delivery guard)
        # Producer uses a virtual monotonic cycle counter so we never reset on cycle==1
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


# -- Sink 1: Redis online feature store ---------------------------------------

class RedisSinkFunction(MapFunction):
    """Writes each FeatureVector to Redis via MapFunction (SinkFunction is a
    JavaFunctionWrapper in PyFlink 2.0 and cannot be subclassed in Python)."""

    def open(self, runtime_context: RuntimeContext):
        self._sink = RedisSink(redis_url=os.getenv("REDIS_URL"))

    def map(self, fv: FeatureVector):
        self._sink.write(fv)
        return fv


# -- Sink 2: S3 Parquet offline store -----------------------------------------

class S3CheckpointSink(MapFunction):
    """Buffers FeatureVectors and flushes to S3 Parquet."""

    def open(self, runtime_context: RuntimeContext):
        self._sink = S3ParquetSink()
        self._count = 0

    def map(self, fv: FeatureVector):
        self._sink.add(fv)
        self._count += 1
        if self._count % _FLUSH_EVERY == 0:
            n = self._sink.flush()
            print(f"[s3-sink] Flushed {n} records to Parquet")
        return fv

# -- Redis Streams source -----------------------------------------------------
# NOTE: Solace → Redis is handled by the standalone_consumer (solace-pubsubplus
# Python SDK works perfectly there). PyFlink reads from Redis Streams because
# env.from_collection() with a blocking generator is evaluated at submission
# time in PyFlink 2.0, which deadlocks before the job graph is ever built.

def _redis_event_iter():
    """Fetch one batch of messages from Redis Streams (non-blocking, finite)."""
    import redis
    rc = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=False)
    results = rc.xread({REDIS_STREAM_KEY: "0"}, count=5000)
    if not results:
        return
    for _, fields in results[0][1]:
        raw = fields[b"data"]
        yield raw.decode("utf-8") if isinstance(raw, bytes) else raw


def _build_redis_stream_source(env: StreamExecutionEnvironment):
    return (
        env.from_collection(list(_redis_event_iter()), type_info=Types.STRING())
        .name("redis-stream-source")
        .set_parallelism(1)
    )


# -- Pipeline builder ---------------------------------------------------------

def build_pipeline(local: bool = False) -> None:
    env = StreamExecutionEnvironment.get_execution_environment()

    # Checkpointing -- every 30s, exactly-once
    env.enable_checkpointing(30_000)
    env.get_checkpoint_config().set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)
    env.get_checkpoint_config().set_min_pause_between_checkpoints(10_000)
    env.get_checkpoint_config().set_tolerable_checkpoint_failure_number(2)

    # RocksDB state backend for production (heap is fine for local dev)
    if not local:
        checkpoint_dir = os.getenv("FLINK_CHECKPOINT_DIR")
        if checkpoint_dir:
            try:
                from pyflink.datastream.state_backend import RocksDBStateBackend
                env.set_state_backend(RocksDBStateBackend(checkpoint_dir, incremental_checkpoints=True))
            except Exception as e:
                print(f"[pipeline] RocksDB backend unavailable, using heap: {e}")

    parallelism = int(os.getenv("FLINK_PARALLELISM", "4" if not local else "1"))
    env.set_parallelism(parallelism)

    # -- Source ---------------------------------------------------------------
    # Always read from Redis Streams. When SOLACE_HOST is set, the standalone
    # consumer bridges Solace → Redis so data flows end-to-end.
    print("[pipeline] Reading from Redis Streams source")
    raw_stream = _build_redis_stream_source(env)

    # -- Stage 1: Normalize (stateless) ---------------------------------------
    normalized = (
        raw_stream
        .map(NormalizeMap(), output_type=Types.PICKLED_BYTE_ARRAY())
        .name("minmax-normalization")
    )

    # -- Stage 2: Rolling window (stateful, keyed by engine_id) ---------------
    features = (
        normalized
        .key_by(lambda e: e.engine_id, key_type=Types.STRING())
        .process(RollingWindowProcess(), output_type=Types.PICKLED_BYTE_ARRAY())
        .name("rolling-window-feature-builder")
    )

    # -- Sink 1: Redis online feature store -----------------------------------
    written = features.map(RedisSinkFunction(), output_type=Types.PICKLED_BYTE_ARRAY()).name("redis-online-feature-sink")

    # -- Sink 2: S3 Parquet offline store -------------------------------------
    use_s3 = os.getenv("ENABLE_S3_SINK", "false").lower() == "true"
    if use_s3:
        written.map(S3CheckpointSink(), output_type=Types.PICKLED_BYTE_ARRAY()).name("s3-parquet-offline-sink")

    env.execute("Aircraft Telemetry Feature Pipeline")


if __name__ == "__main__":
    import argparse
    import dotenv

    dotenv.load_dotenv(
        Path(__file__).parents[1] / "config" / "solace.env",
        override=False,
    )

    parser = argparse.ArgumentParser(description="Aircraft Telemetry PyFlink Pipeline")
    parser.add_argument("--local", action="store_true", help="Run in local mini-cluster mode")
    parser.add_argument("--dry-run", action="store_true", help="Validate components without Flink JVM")
    args = parser.parse_args()

    if args.dry_run:
        print("[dry-run] Validating pipeline components...")
        norm = NormalizationFunction(_SCALER_CSV)
        from streaming.pipeline.functions.rolling_window import RollingWindowFunction as RWF
        from streaming.model.engine_event import EngineEvent
        import time as _time
        wf = RWF(window_size=30)
        for i in range(30):
            ev = EngineEvent(
                engine_id="DRY-RUN-1",
                cycle=i + 1,
                event_time_ms=int(_time.time() * 1000),
                sensors={s: float(i) for s in ["s2","s3","s4","s7","s9","s11","s12","s14","s17","s20","s21"]},
            )
            ev = norm.normalize(ev)
            fv = wf.process(ev)
        assert fv is not None, "RollingWindowFunction did not emit a FeatureVector"
        assert len(fv.features) == 30 * 11, f"Expected 330 features, got {len(fv.features)}"
        print(f"[dry-run] NormalizationFunction: OK")
        print(f"[dry-run] RollingWindowFunction: OK -- emitted FeatureVector for engine DRY-RUN-1")
        print(f"[dry-run] FeatureVector shape: ({fv.window_size}, {fv.n_sensors}) = {len(fv.features)} floats")
        print(f"[dry-run] Redis key: {fv.redis_feature_key}")
        print("[dry-run] All pipeline components validated successfully.")
    else:
        build_pipeline(local=args.local)
