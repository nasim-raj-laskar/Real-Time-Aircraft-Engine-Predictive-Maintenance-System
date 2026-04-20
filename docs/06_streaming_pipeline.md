# Streaming Pipeline

## Overview

The streaming pipeline simulates real-time engine telemetry by replaying the C-MAPSS CSV files through Kafka, then processes each event to compute features and store them for inference.

---

## Components

```
CSV Files
    │
    ▼
Kafka Producer (simulator)
    │
    ▼
Kafka Topic: engine_telemetry
    │
    ▼
Feature Engineering Consumer
    │
    ├──► Redis (online feature store)
    └──► S3 / Parquet (offline store)
```

---

## Kafka Producer — Telemetry Simulator

Reads rows from the CSV sequentially and publishes one event per cycle, per engine.

```python
# streaming/producer.py
from confluent_kafka import Producer
import pandas as pd
import json
import time

COLS = ['unit', 'cycle', 'os1', 'os2', 'os3'] + [f's{i}' for i in range(1, 22)]
TOPIC = 'engine_telemetry'

def make_producer(bootstrap_servers: str = 'localhost:9092') -> Producer:
    return Producer({'bootstrap.servers': bootstrap_servers})

def simulate(dataset_path: str, delay_seconds: float = 0.01):
    producer = make_producer()
    df = pd.read_csv(dataset_path, sep=' +', header=None,
                     usecols=range(26), names=COLS, engine='python')

    # Sort by cycle to simulate time order across all engines
    df = df.sort_values(['cycle', 'unit'])

    for _, row in df.iterrows():
        event = row.to_dict()
        producer.produce(
            topic=TOPIC,
            key=str(int(event['unit'])),
            value=json.dumps(event)
        )
        producer.poll(0)
        time.sleep(delay_seconds)

    producer.flush()
    print(f"Published {len(df)} events")
```

Run:
```bash
python streaming/producer.py --dataset Dataset/train_FD001.txt --delay 0.01
```

---

## Kafka Topic Configuration

```bash
# Create topic
kafka-topics.sh --create \
  --topic engine_telemetry \
  --partitions 6 \
  --replication-factor 1 \
  --bootstrap-server localhost:9092

# Partition by engine_id (key) so all events for one engine go to the same partition
# This ensures ordering per engine without global ordering
```

---

## Feature Engineering Consumer

Consumes telemetry events, maintains per-engine rolling buffers, computes features, writes to Redis.

```python
# streaming/feature_consumer.py
from confluent_kafka import Consumer
import redis
import json
import numpy as np
from collections import deque

TOPIC   = 'engine_telemetry'
WINDOW  = 30
SENSORS = ['s2','s3','s4','s7','s9','s11','s12','s14','s17','s20','s21']
BASELINE_CYCLES = 10

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# In-memory buffers per engine (also backed to Redis for recovery)
buffers   = {}  # engine_id → deque of sensor arrays
baselines = {}  # engine_id → mean sensor array from first 10 cycles

def process_event(event: dict):
    eid   = int(event['unit'])
    cycle = int(event['cycle'])
    sensors = np.array([event[s] for s in SENSORS], dtype=np.float32)

    # Initialize buffer
    if eid not in buffers:
        buffers[eid] = deque(maxlen=WINDOW)

    buffers[eid].append(sensors)

    # Build baseline from first BASELINE_CYCLES cycles
    if cycle <= BASELINE_CYCLES:
        baseline_key = f'engine:{eid}:baseline_acc'
        acc = json.loads(r.get(baseline_key) or '[]')
        acc.append(sensors.tolist())
        r.set(baseline_key, json.dumps(acc))
        if cycle == BASELINE_CYCLES:
            baselines[eid] = np.mean(acc, axis=0)
            r.set(f'engine:{eid}:baseline', json.dumps(baselines[eid].tolist()))
    elif eid not in baselines:
        raw = r.get(f'engine:{eid}:baseline')
        if raw:
            baselines[eid] = np.array(json.loads(raw))

    features = compute_features(eid, sensors)
    r.set(f'engine:{eid}:features', json.dumps(features.tolist()), ex=3600)
    r.set(f'engine:{eid}:last_cycle', cycle)

def compute_features(eid: int, current: np.ndarray) -> np.ndarray:
    buf = np.array(buffers[eid])  # (min(cycle, 30), 11)

    raw   = current
    rmean = buf.mean(axis=0)
    rstd  = buf.std(axis=0)
    slope = compute_slope(buf)
    dev   = current - baselines.get(eid, current)  # deviation from baseline

    return np.concatenate([raw, rmean, rstd, slope, dev])

def compute_slope(buf: np.ndarray) -> np.ndarray:
    if len(buf) < 2:
        return np.zeros(buf.shape[1])
    t = np.arange(len(buf))
    slopes = np.polyfit(t, buf, 1)[0]  # degree-1 coefficient per sensor
    return slopes

def run():
    consumer = Consumer({
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'feature-engineering',
        'auto.offset.reset': 'earliest'
    })
    consumer.subscribe([TOPIC])

    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None or msg.error():
            continue
        event = json.loads(msg.value())
        process_event(event)

if __name__ == '__main__':
    run()
```

---

## Offline Store Writer

In parallel, write all events to S3/Parquet for training data accumulation:

```python
# streaming/offline_writer.py
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
import pandas as pd

BATCH_SIZE = 1000
OUTPUT_DIR = Path('data/offline_store')

class OfflineWriter:
    def __init__(self):
        self.buffer = []

    def write(self, event: dict):
        self.buffer.append(event)
        if len(self.buffer) >= BATCH_SIZE:
            self.flush()

    def flush(self):
        if not self.buffer:
            return
        df = pd.DataFrame(self.buffer)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"batch_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        df.to_parquet(path, index=False)
        self.buffer.clear()
```

---

## Event Schema

Each Kafka message value:

```json
{
  "unit": 12,
  "cycle": 104,
  "os1": -0.0007,
  "os2": -0.0004,
  "os3": 100.0,
  "s1": 518.67,
  "s2": 641.82,
  "s3": 1589.70,
  "s4": 1400.60,
  "s5": 14.62,
  "s6": 21.61,
  "s7": 554.36,
  "s8": 2388.06,
  "s9": 9046.19,
  "s10": 1.30,
  "s11": 47.47,
  "s12": 521.66,
  "s13": 2388.02,
  "s14": 8138.62,
  "s15": 8.4195,
  "s16": 0.03,
  "s17": 392,
  "s18": 2388,
  "s19": 100.00,
  "s20": 39.06,
  "s21": 23.419
}
```

---

## Throughput and Scaling

| Scenario | Events/sec | Partitions | Consumer Instances |
|----------|-----------|------------|-------------------|
| Development (1 dataset) | ~100 | 1 | 1 |
| Production (fleet simulation) | ~10,000 | 6 | 6 |
| High-scale (1000 engines) | ~100,000 | 24 | 24 |

Scale consumers horizontally — each consumer instance handles a subset of partitions. Since events are keyed by engine_id, all cycles for one engine always go to the same consumer, preserving buffer state.

---

## Docker Compose — Kafka Setup

```yaml
zookeeper:
  image: confluentinc/cp-zookeeper:7.5.0
  environment:
    ZOOKEEPER_CLIENT_PORT: 2181

kafka:
  image: confluentinc/cp-kafka:7.5.0
  depends_on: [zookeeper]
  ports:
    - "9092:9092"
  environment:
    KAFKA_BROKER_ID: 1
    KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
```
