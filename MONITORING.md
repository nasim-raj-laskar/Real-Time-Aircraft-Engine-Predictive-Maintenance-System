# Monitoring Stack Setup

This project includes a Prometheus + Grafana monitoring stack for the inference service.

## What is included

- `docker-compose.yml` - full application + monitoring stack definition
- `monitoring/prometheus/prometheus.yml` - Prometheus scrape configuration
- `monitoring/grafana/provisioning/datasources/datasource.yml` - Grafana Prometheus datasource
- `monitoring/grafana/provisioning/dashboards/dashboard.yml` - Grafana dashboard provisioning
- `monitoring/grafana/dashboards/aircraft_engine_monitoring.json` - default monitoring dashboard

## Start the stack

1. Start the full application and monitoring stack together:

```powershell
docker compose up -d
```

> Prometheus and Grafana are now part of the same `docker-compose.yml` network as the inference API and Redis.

2. Open the monitoring UIs:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

4. Grafana login:

- user: `admin`
- password: `admin`

## Verify the stack

- Prometheus target page: `http://localhost:9090/targets`
- Inference metrics endpoint: `http://localhost:8000/metrics`
- Grafana dashboard should load the provisioning dashboard automatically.

## Useful PromQL queries

- Prediction requests by risk level:

```promql
sum by (risk_level) (rate(prediction_requests_total[5m]))
```

- Prediction latency P95:

```promql
histogram_quantile(0.95, sum(rate(prediction_latency_seconds_bucket[5m])) by (le))
```

- Critical engine rate:

```promql
rate(critical_engines_total[5m])
```

- Prediction error rate:

```promql
sum(rate(prediction_errors_total[5m]))
```

## Notes

- `host.docker.internal` is used by Prometheus to scrape the local inference API from Docker on Windows.
- If your API is not available on `http://localhost:8000`, update `monitoring/prometheus/prometheus.yml` accordingly.
