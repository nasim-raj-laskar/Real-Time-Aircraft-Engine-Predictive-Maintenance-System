# System Architecture

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Data["Data Layer"]
        A[NASA C-MAPSS FD001] --> B[S3 Bronze\nraw files]
        B --> C[S3 Silver\nParquet + scaler]
        C --> D[S3 Gold\nNumPy sequences]
    end

    subgraph Pipeline["ML Pipeline — 7 Stages"]
        D --> E[GRU Training\n3-layer 128→64→32]
        E --> F[Evaluation\nRMSE · NASA · F1]
        F --> G{Quality Gates\nRMSE < 20\nNASA < 2000}
        G -->|Pass| H[MLflow Registry\nDagsHub]
        G -->|Fail| E
        H --> I[S3 Artifacts\nmodel.keras · scaler.pkl]
    end

    subgraph Stream["Streaming Pipeline"]
        J[Telemetry Producer\n100 engines\nrisk-distributed] --> K[Redis Streams\ndefault transport]
        K --> L[Standalone Consumer\nor PyFlink cluster]
        L --> M[Redis Feature Store\nengine:id:features]
        L --> N[S3 Parquet\noffline store]
    end

    subgraph Infer["Inference Service"]
        I --> O[FastAPI :8000\nREST + WS + SSE]
        M --> O
    end

    subgraph UI["Frontend"]
        O --> Q[Vue 3 Dashboard\n5 pages · 3 WS streams]
    end

    subgraph Mon["Monitoring"]
        O --> R[Prometheus :9090]
        R --> S[Grafana :3000\n15+ panels]
        T[Evidently AI 0.7\nKS-test drift] --> U[HTML Reports\nserved via API]
        U --> Q
    end

    style G fill:#FFD700,stroke:#333,stroke-width:2px
    style H fill:#90EE90,stroke:#333,stroke-width:2px
    style O fill:#87CEEB,stroke:#333,stroke-width:2px
    style Q fill:#DDA0DD,stroke:#333,stroke-width:2px
```

---

## Data Flow

```mermaid
sequenceDiagram
    participant CSV as FD001 Dataset
    participant PROD as Telemetry Producer
    participant RS as Redis Stream
    participant CONS as Standalone Consumer
    participant R as Redis Feature Store
    participant S3 as S3 Parquet
    participant API as FastAPI
    participant Model as GRU (batch)
    participant WS as WebSocket Clients

    CSV->>PROD: Read rows · risk-distributed lifecycle offsets
    PROD->>RS: XADD telemetry:stream {engine_id, cycle, sensors}
    RS->>CONS: XREAD batch 200 msgs · 1s block

    CONS->>CONS: NormalizationFunction (MinMax stateless)
    CONS->>CONS: RollingWindowFunction (30-cycle keyed buffer)
    CONS->>R: SET engine:{id}:features (float32 bytes · TTL 1h)
    CONS->>R: HSET engine:{id}:meta {cycle, event_time}
    CONS->>S3: Parquet flush every 500 vectors

    Note over API: WebSocket prediction loop (every 5s)
    API->>R: KEYS engine:*:features → list active engines
    API->>R: GET engine:{id}:features for each
    API->>Model: Single batched forward pass (N, 30, 11)
    Model-->>API: RUL predictions array
    API->>API: Record Prometheus metrics
    API->>WS: Broadcast predictions + alerts

    Note over API: On-demand retraining
    API->>API: POST /pipeline/run → subprocess main.py
    API->>WS: SSE stream pipeline logs
```

---

## Streaming Pipeline Detail

```mermaid
flowchart LR
    subgraph Producer
        A[FD001 rows\nper-engine grouped] --> B[Risk-distributed\nlifecycle offset\n70/10/10/10]
        B --> C[Virtual monotonic\ncycle counter\nper engine]
        C --> D{Transport}
        D -->|default| E[Redis XADD\ntelemetry:stream]
        D -->|SOLACE_HOST set| F[Solace PubSub+\naircraft/engine/*/telemetry/cycle]
    end

    subgraph Consumer
        E --> G[XREAD batch]
        F --> G
        G --> H[NormalizationFunction\nMinMax stateless]
        H --> I[RollingWindowFunction\n30-cycle keyed deque]
        I --> J{Window full?}
        J -->|yes| K[RedisSink\nengine:id:features]
        J -->|yes| L[S3ParquetSink\nflush every 500]
        J -->|no| M[accumulate]
    end

    subgraph Inference
        K --> N[FastAPI\n/predict/engine/id\n/ws/predictions]
    end
```

---

## Inference Service Architecture

```mermaid
flowchart TB
    subgraph Pathways["Prediction Pathways"]
        A[POST /predict\nnormalized 30×11] --> D
        B[POST /predict/raw\nraw sensor dicts] --> E[InferencePreprocessor\nscaler.transform] --> D
        C[GET /predict/engine/id\nRedis feature store] --> D
        F[POST /push → buffer\nGET /predict/stream/id] --> D
        D[GRU Model\nbatch forward pass\ntraining=False]
    end

    subgraph WS["WebSocket Streams"]
        G[/ws/predictions\n5s · all Redis engines\nbatched inference]
        H[/ws/telemetry\n2s · engine metadata]
        I[/ws/alerts\n5s · HIGH+CRITICAL only]
    end

    subgraph Retrain["Pipeline Retraining"]
        J[POST /pipeline/run\nnon-blocking subprocess]
        K[GET /pipeline/status\nidle/running/success/failed]
        L[GET /pipeline/logs\nSSE line stream]
    end

    D --> G & I
    G --> PROM[Prometheus metrics\nactive_engines · requests\nlatency · critical_gauge]
```

---

## Redis Key Schema

```mermaid
erDiagram
    FEATURE_STORE {
        bytes engine_id_features "float32 tensor 30x11 = 1320 bytes · TTL 3600s"
        hash engine_id_meta "cycle · event_time · window_size · n_sensors · TTL 3600s"
        list engine_id_buffer "JSON sensor readings push pathway · TTL 3600s"
        stream telemetry_stream "Raw EngineEvent JSON · maxlen 50000"
    }
```

---

## Frontend Architecture

```mermaid
flowchart TB
    subgraph Pages["Vue 3 Pages"]
        P1[FleetPage /]
        P2[EnginePage /engine/:id]
        P3[PipelinePage /pipeline]
        P4[MLOpsPage /mlops]
        P5[ReplayPage /replay]
    end

    subgraph State["Pinia Stores"]
        ES[engineStore\npredictions · telemetry · modelInfo]
        AS[alertStore\nalerts · acks]
    end

    subgraph Transport
        WS[useWebSockets\n3 streams]
        REST[api.ts Axios]
        SSE[EventSource\n/pipeline/logs]
        POLL[fetch polling\n/predict/stream/id]
    end

    subgraph Backend
        API[FastAPI :8000]
        NGINX[nginx :80\nproxy → :8000]
    end

    P1 & P2 & P3 & P4 & P5 --> ES & AS
    WS & REST --> ES & AS
    SSE --> P4
    POLL --> P5
    NGINX --> API
```

---

## Deployment Architecture

```mermaid
graph TB
    subgraph Docker["Docker Compose — 13 services"]
        subgraph Broker["Event Broker"]
            SOL[Solace PubSub+\n:8080 :55555]
        end

        subgraph Streaming["Stream Processing"]
            PROD[telemetry-producer\nRisk-distributed · Redis Streams]
            CONS[standalone-consumer\nNormalize → Window → Redis]
        end

        subgraph Store["Feature Store"]
            RD[Redis :6379\nFeatures + Buffer + Stream]
        end

        subgraph ML["ML Services"]
            API[inference-api :8000\nFastAPI + Retraining + Drift]
            FLINK[Flink :8082\ncluster mode optional]
        end

        subgraph FE["Frontend"]
            FRONT[frontend :5173\nVue 3 + nginx]
        end

        subgraph Mon["Monitoring"]
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
    FRONT --> API
```

---

## Monitoring Architecture

```mermaid
flowchart TB
    subgraph Sources
        A[FastAPI /metrics\nall 9 Prometheus metrics]
        B[node-exporter :9100\nCPU · memory · disk · network]
        C[redis-exporter :9121\nclients · memory · commands/s]
    end

    subgraph Collection
        D[Prometheus\n15s scrape interval]
    end

    subgraph Visualization
        E[Grafana\n15+ panels · auto-provisioned]
    end

    subgraph MLMonitoring["ML Monitoring"]
        F[Evidently AI 0.7\nKS-test + DataDriftPreset]
        G[reports/drift/*.html\nserved via /drift/reports/]
        H[MLOps page iframe\ninteractive dashboard]
    end

    subgraph Alerting
        I[alerting_rules.yml\nCriticalEngine · HighLatency\nHighErrorRate · APIDown · RedisMemory]
    end

    A & B & C --> D
    D --> E
    D --> I
    F --> G --> H
```
