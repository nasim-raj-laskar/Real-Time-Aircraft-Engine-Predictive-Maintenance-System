# Feature Engineering

## Overview

The feature engineering stage transforms preprocessed sensor data into sliding window sequences ready for GRU input.

```mermaid
mindmap
  root((Feature Engineering))
    Input
      11 useful sensors
      Normalized to 0-1
      Grouped by engine
    Sequence Building
      Sliding window size 30
      Step size 1 cycle
      Padding for short engines
    Target
      RUL normalized by 125
      Sigmoid output range 0-1
    Output
      X shape n × 30 × 11
      y shape n
```

---

## Sliding Window Sequences

The core step: for each engine, slide a window of 30 cycles across its history. Each window becomes one training sample.

```mermaid
flowchart LR
    subgraph Engine["Engine ENG-042 (206 cycles)"]
        direction LR
        W1["Window 1\ncycles 1–30\n→ label: RUL@30"] --> W2["Window 2\ncycles 2–31\n→ label: RUL@31"]
        W2 --> W3["..."]
        W3 --> WN["Window 177\ncycles 177–206\n→ label: RUL@206 = 0"]
    end

    WN --> OUT["X: (177, 30, 11)\ny: (177,)"]

    style OUT fill:#90EE90,stroke:#333,color:#000
```

**Output shape per engine:** `(n_cycles - window_size + 1, 30, 11)`

---

## Test Set — Last Window Only

For test data, only the **last 30 cycles** per engine are used (the model predicts RUL at the most recent observation).

Engines with fewer than 30 cycles are zero-padded at the front.

---

## Target Normalization

RUL values are normalized to `[0, 1]` to match the Sigmoid output:

```
y_normalized = RUL / 125
```

At inference, denormalize: `RUL_cycles = model_output × 125`

---

## Data Split Strategy

```mermaid
flowchart TD
    ALL[All 100 engines] --> GSS[GroupShuffleSplit\nby engine unit\ntest_size=0.2]
    GSS --> TR[80 engines → Training sequences]
    GSS --> VA[20 engines → Validation sequences]

    TR --> XTR["X_train: (~16k, 30, 11)\ny_train: (~16k,)"]
    VA --> XVA["X_val: (~4k, 30, 11)\ny_val: (~4k,)"]

    style XTR fill:#90EE90,stroke:#333,color:#000
    style XVA fill:#87CEEB,stroke:#333,color:#000
```

Engines stay intact — all cycles from one engine go to either train or val, never split across both.

---

## Configuration

| Parameter | Value | Location |
|-----------|-------|----------|
| window_size | 30 | `config/features.yaml` |
| test_size | 0.2 | `config/features.yaml` |
| rul_clip | 125 | `config/transform.yaml` |

---

## Output Artifacts

```
artifacts/data_feature_engineering/
├── X_train.npy          (n_train, 30, 11)
├── y_train.npy          (n_train,)
├── X_val.npy            (n_val, 30, 11)
├── y_val.npy            (n_val,)
├── X_test.npy           (n_test, 30, 11)
├── y_test.npy           (n_test,)
└── feature_config.json  window_size, features list, rul_clip, scaler_path
```

---

## Streaming Feature Engineering

In the real-time pipeline, features are built incrementally per engine:

```mermaid
sequenceDiagram
    participant P as Producer
    participant RS as Redis Stream
    participant C as Consumer
    participant R as Redis Feature Store
    participant API as FastAPI

    P->>RS: XADD engine_id · cycle · sensors
    RS->>C: XREAD batch
    C->>C: NormalizationFunction (MinMax stateless)
    C->>C: RollingWindowFunction (30-cycle keyed buffer)
    C->>R: SET engine:id:features (float32 bytes)
    R->>API: GET at inference time
```

The `RollingWindowFunction` maintains a per-engine deque of the last 30 normalized sensor rows. When the buffer reaches 30 entries it emits a `FeatureVector` identical in shape to `X_test` — the same model reads both.
