# System Architecture

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Data Layer
        A[NASA C-MAPSS Dataset] --> B[S3 Bronze Layer]
        B --> C[S3 Silver Layer]
        C --> D[S3 Gold Layer]
    end

    subgraph ML Pipeline
        D --> E[GRU Training]
        E --> F[Evaluation]
        F --> G{Quality Gates}
        G -->|Pass| H[MLflow Registry]
        G -->|Fail| E
        H --> I[S3 Artifacts]
    end

    subgraph Streaming
        J[Telemetry Producer] --> K[Redis Stream / Solace PubSub+]
        K --> L[Standalone Consumer / PyFlink]
        L --> M[Redis Feature Store]
        L --> N[S3 Parquet Offline]
    end

    subgraph Inference
        I --> O[FastAPI Service]
        M --> O
        O --> P[REST + WebSocket + SSE API]
    end

    subgraph Frontend
        P --> Q[Vue 3 Dashboard — 5 pages]
    end

    subgraph Monitoring
        P --> R[Prometheus]
        R --> S[Grafana]
        T[Evidently AI] --> U[Drift Reports → API]
        U --> Q
    end

    style G fill:#FFD700,stroke:#333,stroke-width:2px
    style H fill:#90EE90,stroke:#333,stroke-width:2px
    style O fill:#87CEEB,stroke:#333,stroke-width:2px
    style Q fill:#DDA0DD,stroke:#333,stroke-width:2px
```

---

## Data Flow Architecture

```mermaid
sequenceDiagram
    participant CSV as FD001 Dataset
    participant PROD as Telemetry Producer
    participant RS as Redis Stream
    participant CONS as Standalone Consumer
    participant R as Redis Feature Store
    participant S3 as S3 Parquet
    participant API as FastAPI
    participant Model as GRU (MC Dropout)
    participant WS as WebSocket Clients

    CSV->>PROD: Read row by row (loops forever + Gaussian noise)
    PROD->>RS: XADD telemetry:stream {engine_id, cycle, sensors}
    RS->>CONS: XREAD batch (200 msgs, 1s block)

    CONS->>CONS: NormalizationFunction (MinMax per event)
    CONS->>CONS: RollingWindowFunction (30-cycle keyed buffer)
    CONS->>R: SET engine:{id}:features (float32 bytes)
    CONS->>R: HSET engine:{id}:meta {cycle, event_time}
    CONS->>S3: Parquet flush every 500 vectors

    Note over API: WebSocket prediction loop (5s)
    API->>R: KEYS engine:*:meta → list active engines
    API->>R: GET engine:{id}:features for each
    API->>Model: Batched forward pass (N, 30, 11)
    Model-->>API: RUL predictions
    API->>WS: Broadcast predictions + alerts

    Note over API: Retraining trigger
    API->>API: POST /pipeline/run → subprocess main.py
    API->>WS: SSE stream pipeline logs
```

---

## Streaming Pipeline Detail

```mermaid
flowchart LR
    subgraph Producer
        A[FD001 rows] --> B[Add Gaussian noise]
        B --> C{Transport}
        C -->|default| D[Redis XADD\ntelemetry:stream]
        C -->|SOLACE_HOST set| E[Solace PubSub+\naircraft/engine/*/telemetry/cycle]
    end

    subgraph Consumer
        D --> F[XREAD batch]
        E --> F
        F --> G[NormalizationFunction\nMinMax stateless]
        G --> H[RollingWindowFunction\n30-cycle keyed buffer]
        H --> I{Window full?}
        I -->|yes| J[RedisSink\nengine:id:features]
        I -->|yes| K[S3ParquetSink\nflush every 500]
        I -->|no| L[accumulate]
    end

    subgraph Inference
        J --> M[FastAPI\n/predict/engine/id\n/ws/predictions]
    end
```

**Standalone consumer** (`streaming/pipeline/standalone_consumer.py`) — pure Python, no Flink cluster needed. Default mode.

**PyFlink pipeline** (`streaming/pipeline/telemetry_pipeline.py`) — cluster mode with exactly-once checkpointing, RocksDB state backend, Solace JCSMP connector.

---

## Inference Service Architecture

```mermaid
flowchart TB
    subgraph Prediction Pathways
        A[POST /predict\nnormalized 30×11 array] --> D
        B[POST /predict/raw\nraw sensor dicts] --> E[InferencePreprocessor\nscaler.transform] --> D
        C[GET /predict/engine/id\nRedis feature store] --> D
        F[POST /push → buffer\nGET /predict/stream/id] --> D
        D[MC Dropout\n30 forward passes\nmean + confidence]
    end

    subgraph WebSocket Streams
        G[/ws/predictions\n5s — all Redis engines]
        H[/ws/telemetry\n2s — engine metadata]
        I[/ws/alerts\n5s — HIGH+CRITICAL only]
    end

    subgraph Pipeline Retraining
        J[POST /pipeline/run\nnon-blocking subprocess]
        K[GET /pipeline/status\nidle/running/success/failed]
        L[GET /pipeline/logs\nSSE line stream]
    end

    subgraph Drift Reports
        M[GET /drift/reports\nlist HTML files]
        N[GET /drift/reports/filename\nserve HTML]
    end

    D --> G
    D --> I
```

---

## Redis Key Schema

```
engine:{id}:features   bytes     float32 tensor (30×11 = 1320 bytes)   TTL 3600s
engine:{id}:meta       hash      {cycle, event_time, window_size}       TTL 3600s
engine:{id}:buffer     list      JSON sensor readings (push pathway)    TTL 3600s
telemetry:stream       stream    Raw EngineEvent JSON (maxlen 50000)
```

---

## Frontend Architecture

```mermaid
flowchart TB
    subgraph Vue 3 Dashboard
        A[FleetPage /]
        B[EnginePage /engine/:id]
        C[PipelinePage /pipeline]
        D[MLOpsPage /mlops]
        E[ReplayPage /replay]
    end

    subgraph State
        F[engineStore\npredictions, telemetry, modelInfo]
        G[alertStore\nalerts, acknowledgements]
    end

    subgraph Transport
        H[useWebSockets\n/ws/predictions\n/ws/telemetry\n/ws/alerts]
        I[Axios REST\napi.ts]
        J[EventSource SSE\n/pipeline/logs]
        K[fetch polling\n/predict/stream/id]
    end

    subgraph Backend
        L[FastAPI :8000]
        M[nginx proxy :5173→:80]
    end

    A & B & C & D & E --> F & G
    H --> F & G
    I --> F & G
    J --> D
    K --> E
    F & G --> H & I
    M --> L
```

---

## Deployment Architecture

```mermaid
graph TB
    subgraph Docker Compose
        subgraph Event Broker
            SOL[Solace PubSub+\n:8080 :55555]
        end

        subgraph Stream Processing
            PROD[telemetry-producer\nRedis Streams / Solace]
            CONS[standalone-consumer\nNormalize → Window → Redis]
        end

        subgraph Feature Store
            RD[Redis :6379\nFeatures + Buffer + Stream]
        end

        subgraph ML Services
            API[inference-api :8000\nFastAPI + Retraining]
            FLINK[Flink JobManager :8082]
        end

        subgraph Frontend
            FE[frontend :5173\nVue 3 + nginx]
        end

        subgraph Monitoring
            PROM[Prometheus :9090]
            GRAF[Grafana :3000]
            NODE[node-exporter :9100]
            REDEX[redis-exporter :9121]
        end
    end

    PROD --> RD
    RD --> CONS
    CONS --> RD
    RD --> API
    API --> PROM
    NODE --> PROM
    REDEX --> PROM
    PROM --> GRAF
    FE --> API
```

---

## Monitoring Architecture

```mermaid
flowchart TB
    subgraph Sources
        A[FastAPI /metrics]
        B[node-exporter :9100]
        C[redis-exporter :9121]
    end

    subgraph Collection
        D[Prometheus scraper\n15s interval]
    end

    subgraph Visualization
        E[Grafana\n15+ panels]
    end

    subgraph ML Monitoring
        F[Evidently AI 0.7\nKS-test + DataDriftPreset]
        G[reports/drift/*.html\nserved via /drift/reports/]
        H[MLOps page iframe\ninteractive dashboard]
    end

    subgraph Alerting
        I[alerting_rules.yml\nCriticalEngine, HighLatency\nHighErrorRate, APIDown, RedisMemory]
    end

    A & B & C --> D
    D --> E
    D --> I
    F --> G --> H
```
