"""
Telemetry producer — replays C-MAPSS FD001 rows as EngineEvent JSON.

Default mode: pushes events directly into a Python queue (no broker needed).
Set SOLACE_HOST env var to publish to a real Solace PubSub+ broker instead.

Usage:
    python -m streaming.producer.telemetry_producer
    python -m streaming.producer.telemetry_producer --dataset Dataset/train_FD001.txt --throttle 0
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

# Module-level queue used when no broker is configured
_local_queue: queue.Queue = queue.Queue(maxsize=10_000)


def get_local_queue() -> queue.Queue:
    return _local_queue


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


def run_producer(
    dataset_path: str = "Dataset/train_FD001.txt",
    throttle_ms: int = 1,
    target_queue: queue.Queue = None,
) -> int:
    """
    Replay FD001 rows as EngineEvent JSON.

    Args:
        dataset_path: Path to raw FD001 text file.
        throttle_ms:  Sleep between publishes (0 = max throughput).
        target_queue: Queue to push into. Defaults to module-level _local_queue.

    Returns:
        Number of events emitted.
    """
    q = target_queue if target_queue is not None else _local_queue
    lines = Path(dataset_path).read_text().splitlines()
    emitted = 0

    solace_host = os.getenv("SOLACE_HOST")
    publisher = None

    if solace_host:
        publisher = _build_solace_publisher(solace_host)

    print(f"[producer] Replaying {len(lines)} cycles from {dataset_path}")

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 26:
            continue

        payload = _build_payload(parts)
        raw = json.dumps(payload)

        if publisher:
            _solace_publish(publisher, payload["engine_id"], raw)
        else:
            try:
                q.put_nowait(raw.encode())
            except queue.Full:
                # Back-pressure: wait until space is available
                q.put(raw.encode())

        emitted += 1

        if throttle_ms > 0:
            time.sleep(throttle_ms / 1000)

        if emitted % 1_000 == 0:
            print(f"[producer] Emitted {emitted} events")

    if publisher:
        _solace_disconnect(publisher)

    print(f"[producer] Done. Emitted {emitted} total events.")
    return emitted


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
    parser.add_argument("--throttle", type=int, default=1, help="ms between events (0=max)")
    args = parser.parse_args()
    run_producer(dataset_path=args.dataset, throttle_ms=args.throttle)
