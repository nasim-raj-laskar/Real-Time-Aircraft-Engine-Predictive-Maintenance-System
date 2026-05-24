"""
Standalone Python consumer — full streaming pipeline without a Flink cluster.

Reads EngineEvent JSON from either:
  - The in-process queue populated by telemetry_producer (default / local dev)
  - A Solace PubSub+ durable queue (set SOLACE_HOST env var)

Pipeline stages:
  1. Deserialize EngineEvent
  2. NormalizationFunction  (stateless MinMax)
  3. RollingWindowFunction  (per-engine keyed state, window=30)
  4. RedisSink              (online feature store)
  5. S3ParquetSink          (offline store, flush every FLUSH_EVERY vectors)

Usage:
    # Terminal 1 — start consumer
    python -m streaming.pipeline.standalone_consumer

    # Terminal 2 — start producer
    python -m streaming.producer.telemetry_producer
"""

import os
import signal
import sys
from pathlib import Path

from streaming.model.engine_event import EngineEvent
from streaming.pipeline.functions.normalization import NormalizationFunction
from streaming.pipeline.functions.rolling_window import RollingWindowFunction
from streaming.pipeline.sinks.redis_sink import RedisSink
from streaming.pipeline.sinks.s3_parquet_sink import S3ParquetSink
from streaming.producer.telemetry_producer import get_local_queue

FLUSH_EVERY = int(os.getenv("FLUSH_EVERY", "500"))
SCALER_CSV = Path(__file__).parents[2] / "streaming" / "src" / "main" / "resources" / "scaler_params.csv"

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

    solace_host = os.getenv("SOLACE_HOST")
    receiver = _build_solace_receiver() if solace_host else None
    q = get_local_queue() if not receiver else None

    processed = 0
    fv_emitted = 0

    print("[consumer] Listening for telemetry events…")

    while _running:
        raw = _receive(receiver, q)
        if raw is None:
            continue

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

            if receiver:
                _ack(receiver, raw)

            processed += 1

            if processed % 1_000 == 0:
                print(
                    f"[consumer] processed={processed} "
                    f"fv_emitted={fv_emitted} "
                    f"active_engines={len(windower.active_engines())}"
                )

        except Exception as exc:
            print(f"[consumer] Error: {exc}", file=sys.stderr)
            if receiver:
                _nack(receiver, raw)

    # Graceful shutdown
    if s3_sink:
        s3_sink.close()
    redis_sink.close()
    if receiver:
        _disconnect(receiver)

    print(f"[consumer] Stopped. processed={processed} fv_emitted={fv_emitted}")


# ── Queue helpers ─────────────────────────────────────────────────────────────

def _receive(receiver, q):
    if receiver:
        return _solace_receive(receiver)
    try:
        return q.get(timeout=1.0)
    except Exception:
        return None


def _ack(receiver, raw):
    try:
        receiver[1].ack(raw)
    except Exception:
        pass


def _nack(receiver, raw):
    try:
        receiver[1].nack(raw)
    except Exception:
        pass


def _disconnect(receiver):
    try:
        receiver[1].terminate()
        receiver[0].disconnect()
    except Exception:
        pass


# ── Optional Solace integration ───────────────────────────────────────────────

def _build_solace_receiver():
    try:
        from solace.messaging.messaging_service import MessagingService
        from solace.messaging.resources.queue import Queue
        from solace.messaging.config.solace_properties import (
            transport_layer_properties as TL,
            service_properties as SP,
            authentication_properties as AUTH,
        )
        service = MessagingService.builder().from_properties({
            TL.HOST: os.getenv("SOLACE_HOST"),
            SP.VPN_NAME: os.getenv("SOLACE_VPN", "default"),
            AUTH.SCHEME_BASIC_USER_NAME: os.getenv("SOLACE_USERNAME", "admin"),
            AUTH.SCHEME_BASIC_PASSWORD: os.getenv("SOLACE_PASSWORD", "admin"),
        }).build()
        service.connect()
        q = Queue.durable_exclusive_queue(os.getenv("SOLACE_QUEUE_NAME", "flink.feature.processor"))
        recv = service.create_persistent_message_receiver_builder().build(q)
        recv.start()
        return (service, recv)
    except ImportError:
        print("[consumer] solace-pubsubplus not installed — using local queue")
        return None


def _solace_receive(receiver_tuple):
    _, recv = receiver_tuple
    msg = recv.receive_message(timeout=1_000)
    if msg is None:
        return None
    return msg.get_payload_as_bytes()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--s3", action="store_true", help="Enable S3 Parquet sink")
    args = parser.parse_args()
    run_consumer(use_s3=args.s3)
