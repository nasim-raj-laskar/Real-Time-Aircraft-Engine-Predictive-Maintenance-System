# Project Structure

## Directory Layout

```
Real-Time-Aircraft-Engine-Predictive-Maintenance-System/
│
├── Dataset/                        # Raw C-MAPSS files (read-only reference)
│   ├── train_FD001.txt
│   ├── test_FD001.txt
│   ├── RUL_FD001.txt
│   └── Damage Propagation Modeling.pdf
│
├── docs/                           # This documentation (10 files)
│
├── notebook/
│   └── test-rul.ipynb
│
├── config/                         # YAML pipeline configs
│   ├── config.yaml                 # Paths and artifact locations
│   ├── features.yaml               # Sensor columns, window size
│   ├── model.yaml                  # GRU hyperparameters
│   ├── params.yaml                 # Training parameters (epochs, batch size)
│   ├── redis.yaml                  # Redis connection + TTL
│   ├── registor.yaml               # MLflow registry config
│   ├── schema.yaml                 # Data schema validation
│   └── transform.yaml              # Scaler and transformation config
│
├── src/
│   ├── components/                 # 7-stage ML pipeline components
│   │   ├── data_ingestion.py
│   │   ├── data_validation.py
│   │   ├── data_transformation.py
│   │   ├── feature_engineering.py
│   │   ├── model_training.py
│   │   ├── model_evaluation.py
│   │   └── model_registry.py
│   │
│   ├── pipeline/                   # Pipeline stage orchestrators
│   │   ├── data_ingestion_pipeline.py
│   │   ├── data_validation_pipeline.py
│   │   ├── data_transformation_pipeline.py
│   │   ├── feature_engineering_pipeline.py
│   │   ├── model_trainer_pipeline.py
│   │   ├── model_evaluation_pipeline.py
│   │   └── model_registry_pipeline.py
│   │
│   ├── inference/                  # FastAPI inference service
│   │   ├── app.py                  # FastAPI entry point + middleware
│   │   ├── routes.py               # All REST endpoints incl. pipeline + drift
│   │   ├── ws.py                   # WebSocket endpoints (/ws/predictions, telemetry, alerts)
│   │   ├── predictor.py            # MC Dropout inference logic
│   │   ├── preprocessor.py         # Raw sensor → normalized window
│   │   ├── loader.py               # Artifact loading at startup
│   │   ├── buffer.py               # Redis-backed + in-memory push buffer
│   │   ├── feature_store.py        # Redis feature store client
│   │   ├── metrics.py              # Prometheus metric definitions
│   │   └── structured_logger.py    # JSON structured logger
│   │
│   ├── monitoring/
│   │   ├── drift_detector.py       # KS-test drift + Evidently 0.7 HTML reports
│   │   └── drift_monitor.py        # Scheduled drift monitoring runner
│   │
│   ├── cloud/
│   │   └── s3.py                   # S3 client wrapper
│   │
│   ├── metrics/
│   │   ├── scores.py               # RMSE, NASA score
│   │   └── plot.py                 # Evaluation plots
│   │
│   ├── config/
│   │   └── configuration.py        # Config loader (reads YAML files)
│   │
│   ├── entity/
│   │   └── config_entity.py        # Config + request/response dataclasses
│   │
│   ├── utils/
│   │   ├── common.py               # Helper functions (save_json, etc.)
│   │   ├── mlflow_setup.py         # DagsHub + MLflow initialization
│   │   └── suppress_warnings.py
│   │
│   ├── logging/
│   │   └── logger.py               # Pipeline logger (writes to logs/<timestamp>/)
│   │
│   └── exception/
│       └── exception.py            # CustomException with file + line info
│
├── streaming/
│   ├── producer/
│   │   └── telemetry_producer.py   # Loops FD001, adds Gaussian noise, publishes to Redis Streams or Solace
│   │
│   ├── pipeline/
│   │   ├── standalone_consumer.py  # Pure Python consumer (no Flink needed)
│   │   ├── telemetry_pipeline.py   # PyFlink entry point (cluster mode)
│   │   ├── functions/
│   │   │   ├── normalization.py    # Stateless MinMax per event
│   │   │   └── rolling_window.py   # Per-engine 30-cycle keyed buffer
│   │   └── sinks/
│   │       ├── redis_sink.py       # Writes engine:{id}:features
│   │       └── s3_parquet_sink.py  # Flushes every FLUSH_EVERY vectors
│   │
│   ├── model/
│   │   ├── engine_event.py         # EngineEvent dataclass
│   │   └── feature_vector.py       # FeatureVector dataclass + serialization
│   │
│   └── config/
│       └── solace.env              # Solace broker connection config
│
├── frontend/                       # Vue 3 + Vite + TypeScript dashboard
│   └── src/
│       ├── pages/
│       │   ├── FleetPage.vue       # / — Fleet Command Center
│       │   ├── EnginePage.vue      # /engine/:id — Engine Detail
│       │   ├── PipelinePage.vue    # /pipeline — Pipeline Monitor
│       │   ├── MLOpsPage.vue       # /mlops — ML Observability + Retraining
│       │   └── ReplayPage.vue      # /replay — Simulation Lab
│       ├── stores/
│       │   ├── engineStore.ts      # Predictions, telemetry, model info
│       │   └── alertStore.ts       # Alert list + acknowledgement
│       ├── composables/
│       │   └── useWebSockets.ts    # Connects all 3 WS streams
│       ├── services/
│       │   ├── api.ts              # Axios REST + pipeline/drift API calls
│       │   └── websocket.ts        # WS factory
│       └── types/
│           └── index.ts            # TypeScript interfaces
│
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml          # Scrape config (inference-api, node, redis)
│   │   └── alerting_rules.yml      # Alert rules
│   └── grafana/
│       ├── dashboards/
│       │   └── aircraft_engine_monitoring.json   # 15+ panel dashboard
│       └── provisioning/           # Auto-provisioning config
│
├── scripts/
│   ├── export_scaler_params.py     # Exports scaler min/max to CSV for streaming consumer
│   ├── install_flink.sh            # PyFlink installation helper
│   └── provision_solace_queues.sh  # Creates Solace queues via SEMP API
│
├── reports/
│   └── drift/                      # Evidently HTML drift reports (mounted into container)
│
├── artifacts/                      # Generated by pipeline (mounted read-write into container)
│   ├── data_ingestion/data/
│   ├── data_validation/status.json
│   ├── data_transformation/
│   │   ├── processed/              # train/test Parquet
│   │   └── scaler.pkl
│   ├── data_feature_engineering/
│   │   ├── X_train.npy, y_train.npy, X_val.npy, y_val.npy, X_test.npy, y_test.npy
│   │   └── feature_config.json
│   ├── model_trainer/
│   │   ├── model.keras
│   │   └── history.json
│   └── model_evaluation/
│       ├── metrics.json
│       ├── confusion_matrix.png
│       ├── pred_vs_true.png
│       └── error_distribution.png
│
├── logs/                           # Pipeline + inference logs (mounted into container)
│
├── main.py                         # 7-stage ML pipeline runner
├── app.py                          # Uvicorn entry point (imports src/inference/app.py)
├── Dockerfile                      # Inference API image (Python 3.12-slim, multi-stage)
├── Dockerfile.streaming            # Producer + consumer image
├── Dockerfile.frontend             # Vue build + nginx image
├── nginx.conf                      # Reverse proxy (API + WS + drift + pipeline routes)
├── docker-compose.yml              # Full stack orchestration
├── pyproject.toml                  # uv dependency management
└── .env                            # AWS, DagsHub, MLflow credentials
```

---

## 7-Stage ML Pipeline

Run with `python main.py` locally or trigger via `POST /pipeline/run` from the dashboard.

| Stage | Component | Output |
|-------|-----------|--------|
| 1 | Data Ingestion | Raw FD001 files from S3 → `artifacts/data_ingestion/` |
| 2 | Data Validation | Schema + column checks → `artifacts/data_validation/status.json` |
| 3 | Data Transformation | Parquet + scaler → `artifacts/data_transformation/` |
| 4 | Feature Engineering | NumPy sequences → `artifacts/data_feature_engineering/` |
| 5 | Model Training | GRU model + MLflow run → `artifacts/model_trainer/` |
| 6 | Model Evaluation | RMSE, NASA score, F1, plots → `artifacts/model_evaluation/` |
| 7 | Model Registry | MLflow registry + S3 artifacts → `artifacts/model_registry/` |

---

## Docker Stack

```bash
docker compose up -d
```

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `inference-api` | Custom (Dockerfile) | 8000 | FastAPI — inference + retraining + drift |
| `redis` | redis:7-alpine | 6379 | Feature store + stream transport |
| `solace` | solace/solace-pubsub-standard | 8080, 55555 | Event broker |
| `flink-jobmanager` | flink:2.0 | 8082 | Flink Web UI |
| `flink-taskmanager` | flink:2.0 | — | Flink task execution |
| `telemetry-producer` | Custom (Dockerfile.streaming) | — | Streams FD001 → Redis Streams |
| `standalone-consumer` | Custom (Dockerfile.streaming) | — | Consumer → Redis feature store |
| `node-exporter` | prom/node-exporter | 9100 | System metrics |
| `redis-exporter` | oliver006/redis_exporter | 9121 | Redis metrics |
| `prometheus` | prom/prometheus | 9090 | Metrics collection |
| `grafana` | grafana/grafana | 3000 | Dashboards |
| `frontend` | Custom (Dockerfile.frontend) | 5173 | Vue 3 dashboard via nginx |

### Volume Mounts (inference-api)

| Host Path | Container Path | Mode | Purpose |
|-----------|---------------|------|---------|
| `./artifacts` | `/app/artifacts` | rw | Pipeline writes new model artifacts here |
| `./logs` | `/app/logs` | rw | Pipeline + inference logs |
| `./reports` | `/app/reports` | rw | Evidently drift reports served via API |

---

## Environment Setup

```bash
# Install dependencies
uv sync

# Configure credentials in .env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
AWS_S3_BUCKET=aircraft-engine-data
DAGSHUB_TOKEN=...
MLFLOW_TRACKING_URI=https://dagshub.com/...

# Run pipeline locally
python main.py

# Or trigger from dashboard
curl -X POST http://localhost:8000/pipeline/run
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Model architecture | 3-layer GRU (128→64→32) | Handles temporal sequences, lighter than Transformer |
| Confidence estimation | MC Dropout (30 passes) | Uncertainty without separate ensemble |
| RUL clip | 125 cycles | Standard in literature, focuses on degradation window |
| Window size | 30 cycles | Balances temporal context vs. noise |
| Event broker | Solace PubSub+ | Multi-protocol, no ZooKeeper, hardware-accelerated routing |
| Stream transport (local) | Redis Streams | No broker needed for producer↔consumer in same stack |
| Online feature store | Redis | Sub-millisecond reads, TTL-based expiry |
| Offline store | S3 Parquet (Hive-partitioned) | Columnar, efficient for batch retraining reads |
| Model registry | MLflow + DagsHub | Open source, remote tracking, versioning |
| Dependency management | uv | Fast, modern Python package manager |
| Artifacts mount | read-write | Required for in-container retraining |
