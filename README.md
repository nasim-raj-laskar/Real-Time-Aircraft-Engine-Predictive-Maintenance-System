# Real-Time Aircraft Engine Predictive Maintenance System

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.17-orange.svg)](https://www.tensorflow.org/)
[![MLflow](https://img.shields.io/badge/MLflow-Tracking-green.svg)](https://mlflow.org/)
[![Evidently](https://img.shields.io/badge/Evidently-0.7-purple.svg)](https://www.evidentlyai.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-42b883.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-ready Machine Learning system that predicts aircraft engine **Remaining Useful Life (RUL)** using deep learning on NASA's C-MAPSS turbofan engine dataset — with a full real-time streaming pipeline, containerized deployment, on-demand retraining, and a live operations dashboard.

---

## 🎯 Project Overview

- ✅ **Automated ML Pipeline** — 7-stage modular pipeline from data ingestion to model registry
- ✅ **Deep Learning** — 3-layer GRU with MC Dropout confidence estimation, trained on NASA C-MAPSS FD001
- ✅ **MLflow Integration** — Experiment tracking, model registry, versioning on DagsHub
- ✅ **S3 Data Lake** — Medallion architecture (Bronze / Silver / Gold layers)
- ✅ **FastAPI Inference** — REST + WebSocket + SSE API with Prometheus metrics
- ✅ **On-Demand Retraining** — Trigger full pipeline rerun from the dashboard, stream logs live
- ✅ **Streaming Pipeline** — Solace PubSub+ producer, Redis Streams transport, standalone consumer, PyFlink entry point
- ✅ **Redis Feature Store** — Online feature tensors for sub-millisecond inference reads
- ✅ **Drift Detection** — Evidently AI 0.7 interactive HTML reports, served and viewable in-dashboard
- ✅ **Monitoring Stack** — Prometheus + Grafana + Node Exporter + Redis Exporter
- ✅ **Vue 3 Dashboard** — 5-page real-time operations UI with WebSocket streams and simulation lab
- ✅ **Full Docker Stack** — All 13 services containerized and wired in docker-compose

---

## 🏗️ High-Level Architecture

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
        O --> P[REST + WebSocket + SSE]
    end

    subgraph Frontend
        P --> Q[Vue 3 Dashboard — 5 pages]
    end

    subgraph Monitoring
        P --> R[Prometheus]
        R --> S[Grafana]
        T[Evidently AI] --> U[Drift Reports]
        U --> Q
    end

    style G fill:#FFD700,stroke:#333,stroke-width:2px
    style H fill:#90EE90,stroke:#333,stroke-width:2px
    style O fill:#87CEEB,stroke:#333,stroke-width:2px
    style Q fill:#DDA0DD,stroke:#333,stroke-width:2px
```

---

## 📊 Current Model Performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Test RMSE** | 26.15 cycles | < 20 | ❌ |
| **NASA Score** | 2181.2 | < 2000 | ❌ |
| **Accuracy** | 75.0% | > 80% | ❌ |
| **F1 (Weighted)** | 0.643 | > 0.80 | ❌ |

> Trained for 1 epoch as a baseline. Retrain with full epochs via the dashboard **MLOps → Retrain Model** button or `python main.py`. Metrics update live via `/model/evaluation`.

---

## 🚀 Quick Start

### Option A — Full Docker Stack (recommended)

```bash
git clone https://github.com/nasim-raj-laskar/Real-Time-Aircraft-Engine-Predictive-Maintenance-System.git
cd Real-Time-Aircraft-Engine-Predictive-Maintenance-System

cp .env.example .env
# Fill in AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, DAGSHUB_TOKEN, MLFLOW_TRACKING_URI

docker compose up -d
```

| Service | URL |
|---------|-----|
| **Dashboard** | http://localhost:5173 |
| **Inference API** | http://localhost:8000 |
| **Prometheus** | http://localhost:9090 |
| **Grafana** | http://localhost:3000 |
| **Solace Manager** | http://localhost:8080 |
| **Flink Web UI** | http://localhost:8082 |

### Option B — ML Pipeline Only

```bash
uv sync
aws configure
python main.py
```

### Option C — Streaming Pipeline (local, no Flink)

```bash
# Terminal 1 — consumer
python -m streaming.pipeline.standalone_consumer

# Terminal 2 — producer
python -m streaming.producer.telemetry_producer --throttle 50
```

### Option D — Frontend Dev Server

```bash
cd frontend
npm install
npm run dev   # → http://localhost:5173
```

---

## 📁 Project Structure

```
├── src/
│   ├── components/          # 7-stage ML pipeline components
│   ├── pipeline/            # Pipeline stage orchestrators
│   ├── inference/           # FastAPI service
│   │   ├── app.py           # FastAPI entry point + CORS + middleware
│   │   ├── routes.py        # All REST endpoints (predict, pipeline, drift)
│   │   ├── ws.py            # WebSocket streams (predictions, telemetry, alerts)
│   │   ├── predictor.py     # MC Dropout inference
│   │   ├── preprocessor.py  # Raw sensor → normalized window
│   │   ├── buffer.py        # Redis-backed push buffer
│   │   ├── feature_store.py # Redis feature store client
│   │   ├── metrics.py       # Prometheus metric definitions
│   │   └── structured_logger.py
│   ├── monitoring/          # Evidently 0.7 drift detection + scheduled monitor
│   ├── cloud/               # S3 integration
│   └── utils/
│
├── streaming/
│   ├── producer/            # Telemetry producer (Redis Streams + Solace)
│   ├── pipeline/
│   │   ├── standalone_consumer.py  # Pure Python consumer (no Flink needed)
│   │   ├── telemetry_pipeline.py   # PyFlink entry point (cluster mode)
│   │   ├── functions/       # NormalizationFunction, RollingWindowFunction
│   │   └── sinks/           # RedisSink, S3ParquetSink
│   ├── model/               # EngineEvent, FeatureVector dataclasses
│   └── config/              # solace.env
│
├── frontend/                # Vue 3 + Vite + TypeScript dashboard
│   └── src/
│       ├── pages/           # FleetPage, EnginePage, PipelinePage, MLOpsPage, ReplayPage
│       ├── components/      # StatCard, EngineTable, AlertsPanel, charts
│       ├── stores/          # Pinia: engineStore, alertStore
│       ├── composables/     # useWebSockets
│       ├── services/        # api.ts (axios + pipeline/drift calls), websocket.ts
│       └── types/           # TypeScript interfaces
│
├── monitoring/
│   ├── prometheus/          # prometheus.yml, alerting_rules.yml
│   └── grafana/             # Dashboard JSON (15+ panels), provisioning
│
├── scripts/
│   ├── export_scaler_params.py      # Export scaler min/max for streaming consumer
│   ├── install_flink.sh             # PyFlink installation helper
│   └── provision_solace_queues.sh   # Create Solace queues via SEMP API
│
├── reports/drift/           # Evidently HTML drift reports (mounted into container)
├── config/                  # YAML pipeline configs
├── artifacts/               # Generated model artifacts (mounted read-write)
├── docs/                    # Full system documentation (11 docs)
├── Dockerfile               # Inference API image (Python 3.12-slim, multi-stage)
├── Dockerfile.streaming     # Producer + consumer image
├── Dockerfile.frontend      # Vue build + nginx image
├── nginx.conf               # Reverse proxy (API + WS + drift + pipeline routes)
├── docker-compose.yml       # Full 13-service stack
├── app.py                   # Uvicorn entry point
└── main.py                  # 7-stage ML pipeline runner
```

---

## 🔄 ML Pipeline (7 Stages)

| Stage | Component | Output |
|-------|-----------|--------|
| 1 | Data Ingestion | Raw FD001 files from S3 Bronze |
| 2 | Data Validation | Schema + column checks |
| 3 | Data Transformation | Parquet + scaler → S3 Silver |
| 4 | Feature Engineering | NumPy sequences → S3 Gold |
| 5 | Model Training | GRU model + MLflow run |
| 6 | Model Evaluation | RMSE, NASA score, F1, plots |
| 7 | Model Registry | MLflow registry + S3 artifacts |

**Trigger retraining from the dashboard** (MLOps page → Retrain Model button) or via API:

```bash
curl -X POST http://localhost:8000/pipeline/run
curl http://localhost:8000/pipeline/status
curl -N http://localhost:8000/pipeline/logs   # SSE live log stream
```

---

## 🧠 Model Architecture

```
Input:   (batch, 30, 11)       — 30 timesteps, 11 sensors

GRU 128  return_sequences=True
Dropout  0.2
GRU 64   return_sequences=True
Dropout  0.2
GRU 32
Dropout  0.15
Dense 32  ReLU + L2
Dense 16  ReLU + L2
Output 1  Sigmoid  →  RUL in [0, 1]  (denormalize × 125)
```

**Training:** Adam lr=0.0003, batch=256, epochs=150, early stopping, sample weighting for critical engines.

**Confidence:** MC Dropout — 30 forward passes with `training=True`, confidence = `1 - std(preds) × 10`.

---

## 🌊 Streaming Pipeline

```
Telemetry Producer
  └─ reads FD001 rows, adds Gaussian noise each pass, loops forever
  └─ publishes to Redis Stream (default) or Solace PubSub+ (SOLACE_HOST set)

Standalone Consumer  (or PyFlink telemetry_pipeline.py for cluster mode)
  └─ NormalizationFunction   — MinMax per event, reads scaler_params.csv
  └─ RollingWindowFunction   — per-engine 30-cycle keyed buffer
  └─ RedisSink               — writes engine:{id}:features (float32 bytes)
  └─ S3ParquetSink           — flushes every FLUSH_EVERY vectors

FastAPI /predict/engine/{id}
  └─ reads engine:{id}:features from Redis
  └─ GRU MC Dropout → RUL + confidence + risk level
```

---

## 🖥️ Dashboard (Vue 3) — 5 Pages

| Page | Route | What it shows |
|------|-------|---------------|
| **Fleet Command Center** | `/` | Stat cards, risk pie, RUL bar chart, engine table, alerts |
| **Engine Detail** | `/engine/:id` | Risk, RUL, confidence, sensor tags, metadata |
| **Pipeline Monitor** | `/pipeline` | Live topology, service health checks, telemetry feed |
| **ML Observability** | `/mlops` | Model info, metrics, retraining button + live logs, Evidently reports |
| **Replay & Simulation Lab** | `/replay` | Synthetic telemetry, failure injection, live prediction feed |

WebSocket streams: `/ws/predictions` (5s), `/ws/telemetry` (2s), `/ws/alerts` (5s)

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/predict` | Predict from normalized 30×11 array |
| `POST` | `/predict/raw` | Predict from raw sensor dict array |
| `GET`  | `/predict/engine/{id}` | Predict from Redis feature store |
| `GET`  | `/predict/stream/{id}` | Predict from push buffer |
| `POST` | `/predict/batch` | Batch predictions |
| `POST` | `/push` | Push single sensor reading to buffer |
| `GET`  | `/engines` | List all active engines |
| `GET`  | `/engines/{id}` | Engine status + last prediction |
| `GET`  | `/alerts` | Engines at or above risk threshold |
| `GET`  | `/health` | Service health |
| `GET`  | `/model/info` | Model metadata |
| `GET`  | `/model/evaluation` | Live metrics from artifacts |
| `GET`  | `/metrics` | Prometheus scrape endpoint |
| `POST` | `/pipeline/run` | Trigger full ML pipeline retraining |
| `GET`  | `/pipeline/status` | Pipeline run state |
| `GET`  | `/pipeline/logs` | SSE stream of live pipeline logs |
| `GET`  | `/drift/reports` | List Evidently HTML drift reports |
| `GET`  | `/drift/reports/{filename}` | Serve a drift report |
| `WS`   | `/ws/predictions` | Live prediction stream |
| `WS`   | `/ws/telemetry` | Live telemetry metadata stream |
| `WS`   | `/ws/alerts` | Live HIGH/CRITICAL alert stream |

---

## 🛠️ Technology Stack

| Layer | Technologies |
|-------|-------------|
| **ML** | TensorFlow/Keras, NumPy, Pandas, Scikit-learn |
| **MLOps** | MLflow, DagsHub, AWS S3, Boto3 |
| **Inference** | FastAPI, Uvicorn, Redis, Pydantic, MC Dropout |
| **Streaming** | Solace PubSub+, Redis Streams, Apache Flink (PyFlink), PyArrow |
| **Frontend** | Vue 3, Vite, TypeScript, TailwindCSS, ECharts, Pinia, Vue Router |
| **Monitoring** | Prometheus, Grafana, Evidently AI 0.7, Node Exporter, Redis Exporter |
| **Infrastructure** | Docker, nginx, docker-compose |
| **Dev** | uv, Python 3.12, Node 20 |

---

## 📊 MLflow

All training runs tracked at:
```
https://dagshub.com/nasim-raj-laskar/Real-Time-Aircraft-Engine-Predictive-Maintenance-System.mlflow/
```

---

## ☁️ S3 Data Lake

```
s3://aircraft-engine-data/
├── bronze/          raw FD001 files
├── silver/          processed Parquet
├── gold/            NumPy feature arrays
└── artifacts/       model.keras, scaler.pkl, metrics, plots
```

---

## 📚 Documentation

| Doc | Content |
|-----|---------|
| `docs/00_index.md` | Navigation hub + quick reference |
| `docs/01_dataset.md` | C-MAPSS dataset reference |
| `docs/02_preprocessing.md` | Preprocessing pipeline |
| `docs/03_feature_engineering.md` | Sequence building |
| `docs/04_model_training.md` | GRU + MLflow registry |
| `docs/05_inference_service.md` | Full API reference, retraining, Redis schema |
| `docs/06_streaming_pipeline.md` | Solace + Flink pipeline |
| `docs/07_monitoring.md` | Prometheus + Grafana + Evidently 0.7 |
| `docs/07.1_UI.md` | Vue 3 dashboard — 5 pages, stores, WebSocket |
| `docs/08_project_structure.md` | Directory layout, Docker stack |
| `docs/09_architecture.md` | System architecture diagrams |

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

## 📧 Contact

**Nasim Raj Laskar** — [@nasim-raj-laskar](https://github.com/nasim-raj-laskar)

MLflow experiments: [DagsHub](https://dagshub.com/nasim-raj-laskar/Real-Time-Aircraft-Engine-Predictive-Maintenance-System.mlflow/)

---

**Built with ❤️ for Production ML Systems**
