# Monitoring Stack Setup

This project includes a Prometheus + Grafana monitoring stack for the inference service.

## What is included

- `docker-compose.monitoring.yml` - monitoring stack definition
- `monitoring/prometheus/prometheus.yml` - Prometheus scrape configuration
- `monitoring/grafana/provisioning/datasources/datasource.yml` - Grafana Prometheus datasource
- `monitoring/grafana/provisioning/dashboards/dashboard.yml` - Grafana dashboard provisioning
- `monitoring/grafana/dashboards/aircraft_engine_monitoring.json` - default monitoring dashboard

## Start the stack

1. Start the inference API separately if it is not already running:

```powershell
docker compose up -d
```

or run the API directly from Python:

```powershell
uvicorn src.inference.app:app --host 0.0.0.0 --port 8000
```

2. Start Prometheus and Grafana (on the same Docker network as the app):

```powershell
docker compose -f docker-compose.monitoring.yml up -d
```

> This stack uses the existing `aircraft-network` defined by `docker-compose.yml`, so Prometheus can scrape the running app container directly by its container name `aircraft-engine-api`.

If your existing FastAPI container is not yet attached to `aircraft-network`, connect it manually:

```powershell
docker network connect aircraft-network aircraft-engine-api
```

If Redis also needs the same network, connect it too:

```powershell
docker network connect aircraft-network aircraft-redis
```

3. Open the monitoring UIs:

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
