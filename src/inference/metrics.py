from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Request metrics
prediction_requests_total = Counter(
    'prediction_requests_total',
    'Total prediction requests',
    ['engine_id', 'risk_level']
)

prediction_latency_seconds = Histogram(
    'prediction_latency_seconds',
    'Prediction latency in seconds',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

active_engines = Gauge(
    'active_engines_total',
    'Number of engines with recent telemetry'
)

# ML metrics
predicted_rul_cycles = Histogram(
    'predicted_rul_cycles',
    'Distribution of predicted RUL values',
    buckets=[0, 10, 20, 30, 50, 75, 100, 125]
)

failure_risk_score = Histogram(
    'failure_risk_score',
    'Distribution of failure risk scores',
    buckets=[i/10 for i in range(11)]
)

critical_engines_total = Counter(
    'critical_engines_total',
    'Total engines flagged as critical'
)

# Model metrics
model_load_time_seconds = Gauge(
    'model_load_time_seconds',
    'Time taken to load model at startup'
)

prediction_errors_total = Counter(
    'prediction_errors_total',
    'Total prediction errors',
    ['error_type']
)

prediction_confidence = Histogram(
    'prediction_confidence',
    'Distribution of prediction confidence scores',
    buckets=[i/10 for i in range(11)]
)
