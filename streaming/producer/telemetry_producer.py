"""
Telemetry producer — streams EngineEvent JSON continuously.

Default mode: pushes events directly into a Python queue (no broker needed).
Set SOLACE_HOST env var to publish to a real Solace PubSub+ broker instead.

Usage:
    python -m streaming.producer.telemetry_producer
    python -m streaming.producer.telemetry_producer --dataset Dataset/train_FD001.txt --throttle 50
    python -m streaming.producer.telemetry_producer --throttle 0   # max throughput

The producer loops the dataset indefinitely, adding small random noise each
pass so sensor values drift naturally over time — simulating real telemetry.
"""

import argparse
import json
import os
import queue
import time
from datetime import datetime, timezone
from pathlib import Path

from streaming.model.engine_event import SENSOR_NAMES, SENSOR_INDICES

TOPIC_PREFIX = "aircraft/engine/"
TOPIC_SUFFIX = "/telemetry/cycle"

# Module-level queue used when producer and consumer run in the same process
_local_queue: queue.Queue = queue.Queue(maxsize=10_000)

# Redis stream key used when running producer/consumer as separate processes
REDIS_STREAM_KEY = "telemetry:stream"
REDIS_STREAM_MAXLEN = 50_000


def get_local_queue() -> queue.Queue:
    return _local_queue


def _get_redis_client():
    import redis
    return redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=False)


def _build_payload(parts: list) -> dict:
    engine_id = f"ENG-{parts[0]}"
    cycle = int(parts[1])
    return {
        "engine_id": engine_id,
        "cycle": cycle,
        "event_time_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
        "sensors": {
            name: float(parts[idx])
            for name, idx in zip(SENSOR_NAMES, SENSOR_INDICES)
        },
    }


# Small noise scale applied each loop pass so values drift naturally
_NOISE_SCALE = 0.005

# Risk distribution: (lifecycle_start, lifecycle_end, probability)
# ~70% LOW (0-40%), ~10% MED (40-60%), ~10% HIGH (60-80%), ~10% CRIT (80-100%)
_RISK_BUCKETS = [(0.0, 0.40, 0.70), (0.40, 0.60, 0.10), (0.60, 0.80, 0.10), (0.80, 1.0, 0.10)]


def _pick_start_fraction(rng) -> float:
    r = rng.random()
    cumulative = 0.0
    for lo, hi, weight in _RISK_BUCKETS:
        cumulative += weight
        if r < cumulative:
            return rng.uniform(lo, hi)
    return rng.uniform(0.80, 1.0)


def run_producer(
    dataset_path: str = "Dataset/train_FD001.txt",
    throttle_ms: int = 50,
    target_queue: queue.Queue = None,
) -> None:
    """
    Stream FD001 rows as EngineEvent JSON — loops forever.

    Each engine starts at a random lifecycle position so the fleet is spread
    across risk levels (~70% LOW, ~10% MED, ~10% HIGH, ~10% CRITICAL).
    Press Ctrl-C to stop.
    """
    import random as _rng_mod
    q = target_queue if target_queue is not None else _local_queue
    all_lines = [l for l in Path(dataset_path).read_text().splitlines() if len(l.strip().split()) >= 26]

    # Group rows by engine id
    engines: dict = {}
    for line in all_lines:
        parts = line.strip().split()
        engines.setdefault(parts[0], []).append(parts)

    solace_host = os.getenv("SOLACE_HOST")
    publisher = _build_solace_publisher(solace_host) if solace_host else None

    emitted = 0
    loop = 0
    rng = _rng_mod.Random()

    print(f"[producer] {len(engines)} engines loaded from {dataset_path} (loops forever, Ctrl-C to stop)")

    def _publish(payload: dict):
        raw = json.dumps(payload).encode()
        if publisher:
            _solace_publish(publisher, payload["engine_id"], raw.decode())
        elif target_queue is not None:
            try:
                q.put_nowait(raw)
            except queue.Full:
                q.put(raw)
        else:
            _redis_publish(raw)

    # Per-engine state: current dataset index and virtual monotonic cycle counter
    engine_idx    = {eid: int(_pick_start_fraction(rng) * len(rows)) for eid, rows in engines.items()}
    engine_vcycle = {eid: 1 for eid in engines}

    engine_list = list(engines.keys())

    try:
        while True:
            loop += 1
            noise = _NOISE_SCALE * min(loop - 1, 10)

            # Emit one event per engine per tick (round-robin)
            for eid in engine_list:
                rows = engines[eid]
                idx  = engine_idx[eid]
                payload = _build_payload(rows[idx])

                # Virtual monotonic cycle — rolling window never stalls
                payload["cycle"] = engine_vcycle[eid]
                engine_vcycle[eid] += 1

                for k in payload["sensors"]:
                    payload["sensors"][k] += rng.gauss(0, noise) if noise > 0 else 0.0
                _publish(payload)

                # Advance; wrap to a new random lifecycle position at end-of-life
                next_idx = idx + 1
                if next_idx >= len(rows):
                    next_idx = int(_pick_start_fraction(rng) * len(rows))
                engine_idx[eid] = next_idx

                emitted += 1

            # Throttle once per full round (not per engine) — all 100 engines get
            # events in rapid succession, then we sleep once.
            if throttle_ms > 0:
                time.sleep(throttle_ms / 1000)

            if emitted % 5_000 == 0:
                print(f"[producer] Emitted {emitted} events (loop {loop})")

    except KeyboardInterrupt:
        print(f"\n[producer] Stopped. Emitted {emitted} total events across {loop} passes.")
    finally:
        if publisher:
            _solace_disconnect(publisher)


# ── Redis stream publish ─────────────────────────────────────────────────────

_redis_client = None


def _redis_publish(raw: bytes) -> None:
    global _redis_client
    if _redis_client is None:
        _redis_client = _get_redis_client()
    _redis_client.xadd(
        REDIS_STREAM_KEY,
        {"data": raw},
        maxlen=REDIS_STREAM_MAXLEN,
        approximate=True,
    )


# ── Optional Solace integration ───────────────────────────────────────────────

def _build_solace_publisher(host: str):
    try:
        from solace.messaging.messaging_service import MessagingService
        from solace.messaging.config.solace_properties import (
            transport_layer_properties as TL,
            service_properties as SP,
            authentication_properties as AUTH,
        )
        service = MessagingService.builder().from_properties({
            TL.HOST: host,
            SP.VPN_NAME: os.getenv("SOLACE_VPN", "default"),
            AUTH.SCHEME_BASIC_USER_NAME: os.getenv("SOLACE_USERNAME", "admin"),
            AUTH.SCHEME_BASIC_PASSWORD: os.getenv("SOLACE_PASSWORD", "admin"),
        }).build()
        service.connect()
        pub = service.create_persistent_message_publisher_builder().build()
        pub.start()
        return (service, pub)
    except ImportError:
        print("[producer] solace-pubsubplus not installed — falling back to local queue")
        return None


def _solace_publish(publisher_tuple, engine_id: str, raw: str):
    from solace.messaging.resources.topic import Topic
    service, pub = publisher_tuple
    topic = Topic.of(f"{TOPIC_PREFIX}{engine_id}{TOPIC_SUFFIX}")
    msg = service.message_builder().build(raw)
    pub.publish(msg, topic)


def _solace_disconnect(publisher_tuple):
    service, pub = publisher_tuple
    pub.terminate(grace_period=2000)
    service.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="Dataset/train_FD001.txt")
    parser.add_argument("--throttle", type=int, default=50, help="ms between events (default 50 = 20 events/s)")
    args = parser.parse_args()
    run_producer(dataset_path=args.dataset, throttle_ms=args.throttle)
