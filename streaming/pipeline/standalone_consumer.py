"""
Standalone Python consumer — full streaming pipeline without a Flink cluster.

Cross-process transport: Redis Streams (telemetry:stream)
  - Producer XADDs events → consumer XREADs in batches
  - No in-memory queue sharing needed between separate processes

Pipeline stages:
  1. XREAD batch from Redis stream
  2. Deserialize EngineEvent
  3. NormalizationFunction  (stateless MinMax)
  4. RollingWindowFunction  (per-engine keyed state, window=30)
  5. RedisSink              (writes feature tensors to engine:{id}:features)
  6. S3ParquetSink          (optional, flush every FLUSH_EVERY vectors)

Usage:
    # Terminal 1
    python -m streaming.pipeline.standalone_consumer

    # Terminal 2
    python -m streaming.producer.telemetry_producer --throttle 50
"""

import os
import signal
import sys
from pathlib import Path

import redis as _redis

from streaming.model.engine_event import EngineEvent
from streaming.pipeline.functions.normalization import NormalizationFunction
from streaming.pipeline.functions.rolling_window import RollingWindowFunction
from streaming.pipeline.sinks.redis_sink import RedisSink
from streaming.pipeline.sinks.s3_parquet_sink import S3ParquetSink
from streaming.producer.telemetry_producer import REDIS_STREAM_KEY

FLUSH_EVERY = int(os.getenv("FLUSH_EVERY", "500"))
SCALER_CSV = Path(__file__).parents[1] / "src" / "main" / "resources" / "scaler_params.csv"

_running = True


def _shutdown(signum, frame):
    global _running
    print("\n[consumer] Shutting down…")
    _running = False


def run_consumer(use_s3: bool = False) -> None:
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    normalizer = NormalizationFunction(SCALER_CSV)
    windower = RollingWindowFunction(window_size=30)
    redis_sink = RedisSink(redis_url=os.getenv("REDIS_URL"))
    s3_sink = S3ParquetSink() if use_s3 else None

    # Redis stream client
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    rc = _redis.from_url(redis_url, decode_responses=False)
    try:
        rc.ping()
    except Exception as e:
        print(f"[consumer] Cannot connect to Redis at {redis_url}: {e}", file=sys.stderr)
        sys.exit(1)

    # Check for Solace override
    solace_receiver = None
    if os.getenv("SOLACE_HOST"):
        solace_receiver = _build_solace_receiver()

    last_id = "0"  # start from beginning of stream
    processed = 0
    fv_emitted = 0

    if solace_receiver:
        print(f"[consumer] Transport: Solace → Redis Streams bridge active")
    else:
        print(f"[consumer] Transport: Redis Streams at {redis_url}")
    print("[consumer] Waiting for events…")

    while _running:
        if solace_receiver:
            batch = _solace_batch(solace_receiver)
        else:
            batch, last_id = _stream_read(rc, last_id)

        if not batch:
            continue

        for raw in batch:
            try:
                event = EngineEvent.from_json(raw)
                event = normalizer.normalize(event)
                fv = windower.process(event)

                if fv is not None:
                    redis_sink.write(fv)
                    if s3_sink:
                        s3_sink.add(fv)
                    fv_emitted += 1

                    if s3_sink and fv_emitted % FLUSH_EVERY == 0:
                        n = s3_sink.flush()
                        print(f"[consumer] {fv_emitted} vectors emitted, {n} flushed to S3")

                processed += 1

                if processed % 1_000 == 0:
                    print(
                        f"[consumer] processed={processed} "
                        f"fv_emitted={fv_emitted} "
                        f"active_engines={len(windower.active_engines())}"
                    )

            except Exception as exc:
                print(f"[consumer] Error processing event: {exc}", file=sys.stderr)

    if s3_sink:
        s3_sink.close()
    redis_sink.close()
    print(f"[consumer] Stopped. processed={processed} fv_emitted={fv_emitted}")


def _stream_read(rc, last_id: str):
    """XREAD up to 200 messages, blocking 1s. Returns (list[bytes], new_last_id)."""
    try:
        results = rc.xread({REDIS_STREAM_KEY: last_id}, count=200, block=1000)
        if not results:
            return [], last_id
        messages = results[0][1]  # [(msg_id, {b'data': bytes}), ...]
        new_last_id = messages[-1][0]
        if isinstance(new_last_id, bytes):
            new_last_id = new_last_id.decode()
        payloads = [msg[1][b"data"] for msg in messages]
        return payloads, new_last_id
    except Exception as e:
        print(f"[consumer] Stream read error: {e}", file=sys.stderr)
        return [], last_id


# Solace integration 

def _build_solace_receiver():
    import time
    try:
        from solace.messaging.messaging_service import MessagingService
        from solace.messaging.resources.queue import Queue
        from solace.messaging.config.solace_properties import (
            transport_layer_properties as TL,
            service_properties as SP,
            authentication_properties as AUTH,
        )
        props = {
            TL.HOST: os.getenv("SOLACE_HOST"),
            SP.VPN_NAME: os.getenv("SOLACE_VPN", "default"),
            AUTH.SCHEME_BASIC_USER_NAME: os.getenv("SOLACE_USERNAME", "admin"),
            AUTH.SCHEME_BASIC_PASSWORD: os.getenv("SOLACE_PASSWORD", "admin"),
        }
        queue_name = os.getenv("SOLACE_QUEUE_NAME", "flink.feature.processor")
        while True:
            try:
                service = MessagingService.builder().from_properties(props).build()
                service.connect()
                q = Queue.durable_exclusive_queue(queue_name)
                recv = service.create_persistent_message_receiver_builder().build(q)
                recv.start()
                print(f"[consumer] Connected to Solace, consuming from {queue_name}")
                return (service, recv)
            except Exception as e:
                print(f"[consumer] Solace connect/queue error: {e} — retrying in 10s")
                time.sleep(10)
    except ImportError:
        print("[consumer] solace-pubsubplus not installed")
        return None


def _solace_batch(receiver_tuple):
    _, recv = receiver_tuple
    msg = recv.receive_message(timeout=1_000)
    if msg is None:
        return []
    # Try string payload first (Solace text messages), fallback to bytes
    try:
        payload = msg.get_payload_as_string()
        if payload:
            recv.ack(msg)
            return [payload.encode("utf-8")]
    except Exception:
        pass
    payload = msg.get_payload_as_bytes()
    recv.ack(msg)
    return [payload] if payload else []


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--s3", action="store_true", help="Enable S3 Parquet sink")
    args = parser.parse_args()
    run_consumer(use_s3=args.s3)
