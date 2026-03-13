# Real-Time Aircraft Engine Predictive Maintenance System

## Project Goal

Build a production-style Machine Learning system that predicts aircraft engine failure risk and Remaining Useful Life (RUL) using streaming telemetry from engines.

This project demonstrates:

* Streaming ML pipelines
* Feature stores
* Real-time inference
* MLOps practices
* Monitoring and observability

---

# Dataset

## NASA C-MAPSS Turbofan Engine Dataset

Each row represents telemetry collected from an aircraft engine during a flight cycle.

### Columns

engine_id
cycle
operational_setting_1
operational_setting_2
operational_setting_3
sensor_1
sensor_2
...
sensor_21

### Example Row

engine_id,cycle,op1,op2,op3,s1,s2,...,s21
1,1,-0.0007,-0.0004,100.0,518.67,641.82,...,23.419

### Interpretation

engine_id → unique engine
cycle → flight cycle number
sensor_i → engine telemetry (temperature, pressure, vibration etc)

### Prediction Target

Remaining Useful Life (RUL)

RUL = failure_cycle - current_cycle

---

# High-Level System Architecture

```
                    Engine Telemetry CSV
                            |
                            |
                  Kafka Producer (simulator)
                            |
                            |
                       Kafka Topic
                            |
            ----------------------------------
            |                                |
     Feature Engineering Service       Data Lake
            |                                |
            |                                |
      Online Feature Store              Offline Store
            |                                |
            |                                |
        Real-Time Inference API        Model Training
            |
            |
       Prediction Service
            |
            |
     Monitoring + Dashboards
```

---

# Architecture Components

## 1 Data Ingestion (Streaming Simulation)

Because the dataset is static CSV, we simulate telemetry streaming.

### Process

1. Python script reads rows sequentially
2. Each row is sent as a Kafka event
3. Events simulate live engine telemetry

### Example Event

{
"engine_id": 12,
"cycle": 104,
"sensor_3": 642.1,
"sensor_7": 1589.3,
"sensor_12": 23.4
}

### Kafka Topic

engine_telemetry

---

# 2 Stream Processing / Feature Engineering

Kafka consumers process telemetry events.

Raw sensor readings are converted into ML features.

## Example Engineered Features

rolling_temperature_mean
rolling_vibration_std
pressure_trend
sensor_entropy
cycle_delta

### Example Feature Record

engine_id: 12
rolling_temp_mean: 623.4
vibration_std: 0.34
pressure_trend: -0.12

These features are stored in the feature store.

---

# 3 Feature Store

A feature store ensures the same feature logic is used for training and inference.

## Online Feature Store

Purpose: low-latency lookup during inference

Technology options:

Redis
DynamoDB
Postgres (small scale)

Example record

key: engine_12

{
"rolling_temp_mean": 623.4,
"vibration_std": 0.34,
"pressure_trend": -0.12
}

## Offline Feature Store

Purpose: historical storage for training

Technology options

S3
PostgreSQL
Parquet data lake

---

# 4 Model Training Pipeline

Training occurs periodically using historical data.

## Pipeline

Offline Feature Store
|
|
Feature Dataset
|
|
Model Training
|
|
Model Registry

## Candidate Models

XGBoost
LightGBM
RandomForest
LSTM

Recommended baseline:

XGBoost

## Prediction Target

Remaining Useful Life

or

Failure Probability

---

# 5 Real-Time Inference Service

A REST API exposes predictions.

## Request Example

POST /predict

{
"engine_id": 12
}

## Inference Flow

Request
|
|
Feature Store Lookup
|
|
Model Prediction
|
|
Return Result

## Response Example

{
"engine_id": 12,
"remaining_cycles": 38,
"failure_risk": 0.72
}

---

# 6 Monitoring and Observability

Production ML systems require monitoring.

## System Metrics

latency
throughput
CPU usage
memory usage

## ML Metrics

data drift
feature drift
prediction distribution
model confidence

## Monitoring Stack

Prometheus
Grafana
Evidently AI

---

# End-to-End Workflow

Step 1

Dataset CSV → Kafka Producer

Step 2

Kafka topic receives engine telemetry

Step 3

Feature engineering service computes features

Step 4

Features stored in online feature store

Step 5

Inference service retrieves features

Step 6

Model predicts RUL and failure probability

Step 7

Results visualized on monitoring dashboard

---

# Technology Stack

Streaming

Kafka

Feature Store

Redis
S3

ML

XGBoost
Scikit-learn
PyTorch (optional)

Serving

FastAPI

MLOps

MLflow
Airflow
Docker

Monitoring

Prometheus
Grafana

---

# Optional Extensions (Advanced)

Add model retraining pipeline

Detect sensor drift automatically

Add maintenance recommendation engine

Deploy system using Kubernetes

Add CI/CD pipeline for models

---

# Final System Diagram

```
             Engine Telemetry
                    |
                    |
               Kafka Producer
                    |
                    |
                Kafka Topic
                    |
        -----------------------------
        |                           |
 Feature Engineering           Data Lake
        |                           |
        |                           |
 Online Feature Store         Training Pipeline
        |                           |
        |                           |
   Real-Time Inference         Model Registry
        |
        |
    Prediction API
        |
        |
 Monitoring Dashboards
```

---

# What This Project Demonstrates

Industrial predictive maintenance

Streaming machine learning systems

Feature store architecture

Real-time inference

MLOps pipeline design

Monitoring and observability
