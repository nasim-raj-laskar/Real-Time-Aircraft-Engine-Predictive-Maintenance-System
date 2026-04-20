# Monitoring and Observability

## Overview

Production ML systems degrade silently. Monitoring covers three layers:
1. System health (latency, throughput, errors)
2. Data health (sensor drift, feature distribution shift)
3. Model health (prediction drift, confidence degradation)

---

## Monitoring Stack

| Tool | Purpose |
|------|---------|
| Prometheus | Metrics collection and storage |
| Grafana | Dashboards and alerting |
| Evidently AI | ML-specific drift detection |
| Python logging | Structured application logs |

---

## System Metrics (Prometheus)

Instrument the inference service with Prometheus metrics:

```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Request metrics
REQUEST_COUNT    = Counter('predictions_total', 'Total prediction requests', ['engine_id', 'risk_level'])
REQUEST_LATENCY  = Histogram('prediction_latency_seconds', 'Prediction latency', buckets=[.001,.005,.01,.025,.05,.1,.25,.5,1])
ACTIVE_ENGINES   = Gauge('active_engines_total', 'Engines with recent telemetry')

# ML metrics
PREDICTED_RUL    = Histogram('predicted_rul', 'Distribution of RUL predictions', buckets=[0,10,20,30,50,75,100,125])
FAILURE_RISK     = Histogram('failure_risk_score', 'Distribution of failure risk scores', buckets=[i/10 for i in range(11)])
CRITICAL_ALERTS  = Counter('critical_alerts_total', 'Engines flagged as critical')

# Feature store metrics
REDIS_MISS       = Counter('redis_feature_miss_total', 'Feature lookups with no data')
FEATURE_STALENESS = Histogram('feature_age_seconds', 'Age of features at inference time')

start_http_server(8001)  # Prometheus scrapes this port
```

Wrap the predict endpoint:

```python
@app.post("/predict")
def predict(req: PredictRequest):
    with REQUEST_LATENCY.time():
        result = _predict(req)
    REQUEST_COUNT.labels(engine_id=req.engine_id, risk_level=result['risk_level']).inc()
    PREDICTED_RUL.observe(result['remaining_cycles'])
    FAILURE_RISK.observe(result['failure_risk'])
    if result['risk_level'] == 'CRITICAL':
        CRITICAL_ALERTS.inc()
    return result
```

---

## Grafana Dashboards

### Dashboard 1 — Fleet Overview

Panels:
- Active engines count (gauge)
- Risk level distribution (pie chart: LOW / MEDIUM / HIGH / CRITICAL)
- Engines by RUL bucket (bar chart: 0–30, 30–60, 60–90, 90–125)
- Critical engines list (table with engine_id, RUL, risk, last_cycle)
- Prediction throughput (requests/sec over time)

### Dashboard 2 — Single Engine Deep Dive

Panels:
- RUL trend over last 50 cycles (line chart)
- Failure risk trend (line chart with threshold lines at 0.6 and 0.8)
- Sensor readings over time (multi-line: s2, s3, s4, s11, s12)
- Feature deviation from baseline (heatmap)

### Dashboard 3 — System Health

Panels:
- API latency p50/p95/p99 (line chart)
- Redis hit/miss rate
- Kafka consumer lag
- Error rate (5xx responses)

---

## ML Drift Detection (Evidently AI)

### Feature Drift

Compare current feature distributions against the training distribution baseline.

```python
# monitoring/drift_detector.py
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset
import pandas as pd

def run_drift_report(reference_df: pd.DataFrame, current_df: pd.DataFrame) -> dict:
    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference_df, current_data=current_df)
    result = report.as_dict()

    drifted_features = [
        feat for feat, stats in result['metrics'][0]['result']['drift_by_columns'].items()
        if stats['drift_detected']
    ]
    drift_share = result['metrics'][0]['result']['share_of_drifted_columns']

    return {
        'drift_share': drift_share,
        'drifted_features': drifted_features,
        'alert': drift_share > 0.3  # alert if >30% of features drifted
    }
```

Run this on a schedule (e.g., every hour via Airflow) comparing the last hour of inference features against the training set.

### Prediction Drift

Monitor the distribution of predicted RUL values over time. A sudden shift toward low RUL values across the fleet may indicate:
- A real fleet-wide degradation event
- A data pipeline issue (e.g., sensor calibration change)
- Model degradation

```python
from evidently.metrics import ColumnDriftMetric

def check_prediction_drift(historical_preds: list[float], current_preds: list[float]) -> bool:
    ref = pd.DataFrame({'rul': historical_preds})
    cur = pd.DataFrame({'rul': current_preds})
    report = Report(metrics=[ColumnDriftMetric(column_name='rul')])
    report.run(reference_data=ref, current_data=cur)
    return report.as_dict()['metrics'][0]['result']['drift_detected']
```

---

## Alerting Rules

Define in Grafana or Prometheus Alertmanager:

```yaml
# alerting/rules.yml
groups:
  - name: aircraft_engine_alerts
    rules:
      - alert: EngineCriticalRisk
        expr: failure_risk_score_bucket{le="1.0"} - failure_risk_score_bucket{le="0.8"} > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Engine with failure risk > 0.8 detected"

      - alert: HighPredictionLatency
        expr: histogram_quantile(0.95, prediction_latency_seconds_bucket) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "P95 inference latency exceeds 100ms"

      - alert: FeatureDriftDetected
        expr: feature_drift_share > 0.3
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "More than 30% of features show distribution drift"

      - alert: KafkaConsumerLag
        expr: kafka_consumer_lag > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Feature engineering consumer is falling behind"
```

---

## Logging

Use structured JSON logging for easy querying in CloudWatch or ELK:

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'service': 'inference',
            'message': record.getMessage(),
            **getattr(record, 'extra', {})
        })

logger = logging.getLogger('inference')
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# Usage
logger.info("Prediction made", extra={
    'engine_id': 12,
    'rul': 38.2,
    'risk': 0.70,
    'latency_ms': 4.2
})
```

---

## Monitoring Checklist

| Check | Frequency | Alert Threshold |
|-------|-----------|----------------|
| API latency p95 | Continuous | > 100ms |
| Critical engine count | Continuous | > 0 |
| Kafka consumer lag | Every 1 min | > 10,000 messages |
| Redis memory usage | Every 5 min | > 80% |
| Feature drift share | Every 1 hour | > 30% |
| Prediction distribution shift | Every 1 hour | KS test p < 0.05 |
| Model RMSE on new labeled data | Weekly | > 20 cycles |
