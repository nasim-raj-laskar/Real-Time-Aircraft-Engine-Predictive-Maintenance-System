# Monitoring Guide (Simple Version)

## 🎯 What You Have Now

Your API automatically tracks:
- ✅ Request count
- ✅ Response time
- ✅ Predictions (RUL, risk, confidence)
- ✅ Errors
- ✅ Data drift detection

---

## 🚀 Quick Start

### 1. Start API
```bash
start_api.bat
```

### 2. Test It
```bash
uv run python test/test_inference.py
```

### 3. View Metrics
Open: http://localhost:8000/metrics

---

## 📊 What the Metrics Mean

### Request Metrics
```
prediction_requests_total          # How many predictions made
prediction_latency_seconds         # How fast (in seconds)
prediction_errors_total            # How many errors
```

### ML Metrics
```
predicted_rul_cycles               # RUL predictions
failure_risk_score                 # Risk scores (0-1)
critical_engines_total             # Critical engines found
prediction_confidence              # Model confidence
```

### System Metrics
```
model_load_time_seconds            # Startup time
```

---

## 🔍 Data Drift Detection

### What is Drift?
When your production data looks different from training data.

### Check for Drift
```bash
uv run python -m src.monitoring.drift_monitor
```

### Output
```
Drift Share: 15.2%
Alert Level: OK
Drifted Features: s3, s7
```

### Alert Levels
- **OK**: < 30% features changed
- **WARNING**: 30-50% features changed  
- **CRITICAL**: > 50% features changed

### Reports
HTML reports saved to: `reports/drift/`

---

## 📝 Logs

### Where are logs?
`logs/inference.log`

### Log Format (JSON)
```json
{
  "timestamp": "2024-01-15T10:23:45",
  "level": "INFO",
  "engine_id": "ENG-001",
  "rul": 38,
  "risk": 0.70,
  "risk_level": "HIGH",
  "confidence": 0.85,
  "latency_ms": 45.2
}
```

---

## 🐳 Docker (Optional)

### Why Docker?
- Run everything in containers
- Easy deployment
- Includes Redis for caching

### Start with Docker
```bash
# First time only
docker network create aircraft-network

# Start services
docker-compose up -d

# Check status
docker ps

# View logs
docker logs aircraft-engine-api

# Stop
docker-compose down
```

### Services
- **API**: http://localhost:8000
- **Redis**: localhost:6379

---

## 🆘 Troubleshooting

### No metrics showing?
```bash
# Make sure API is running
start_api.bat

# Make at least one prediction
uv run python test/test_inference.py

# Then check metrics
curl http://localhost:8000/metrics
```

### Drift detection fails?
```bash
# Check if training data exists
dir artifacts\data_transformation\processed\train_processed.parquet

# If missing, run training first
python main.py
```

### Docker issues?
```bash
# Check containers
docker ps -a

# View logs
docker logs aircraft-engine-api

# Rebuild
docker-compose build --no-cache
docker-compose up -d
```

---

## 🎯 Summary

**For Local Development:**
```bash
start_api.bat                              # Start API
uv run python test/test_inference.py       # Test
http://localhost:8000/metrics              # View metrics
```

**For Production (Docker):**
```bash
docker-compose up -d                       # Start
docker logs aircraft-engine-api            # Check logs
docker-compose down                        # Stop
```

**That's it!** 🚀
