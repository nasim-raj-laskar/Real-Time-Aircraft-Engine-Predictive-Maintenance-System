# Getting Started - Simple Guide

## 🎯 What's New in Your Project

I added **monitoring** to your inference API. Now it tracks:
- How many predictions you make
- How fast the API responds
- If there are any errors
- Data drift detection

---

## 🚀 How to Use (3 Simple Steps)

### Step 1: Start Your API

```bash
start_api.bat
```

You'll see:
```
Starting Aircraft Engine Inference API...
✓ Model loaded in 2.34s
Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Test Predictions

Open a new terminal and run:
```bash
uv run python test/test_inference.py
```

You'll see predictions like:
```
ENG-0  | Predicted:   45 | True:  112.0 | Risk: MEDIUM   | Confidence: 0.850
ENG-10 | Predicted:   38 | True:   98.0 | Risk: HIGH     | Confidence: 0.823
```

### Step 3: Check Metrics (Optional)

Open your browser: http://localhost:8000/metrics

You'll see metrics like:
```
prediction_requests_total{engine_id="ENG-0",risk_level="MEDIUM"} 1.0
prediction_latency_seconds_sum 0.045
predicted_rul_cycles_sum 45.0
```

**That's it!** ✅

---

## 📊 What Can You Do Now?

### Check API Health
```bash
curl http://localhost:8000/health
```

### Get Model Info
```bash
curl http://localhost:8000/model/info
```

### Make a Prediction
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "engine_id": "ENG-001",
    "sensor_data": [[0.5, 0.6, 0.7, 0.4, 0.6, 0.7, 0.5, 0.6, 0.5, 0.6, 0.6], ...]
  }'
```

### Check for Data Drift
```bash
uv run python -m src.monitoring.drift_monitor
```

This checks if your production data is different from training data.

---

## 🐳 Docker (Optional - For Later)

If you want to run everything in Docker:

```bash
# 1. Create network
docker network create aircraft-network

# 2. Start services
docker-compose up -d

# 3. Check logs
docker logs aircraft-engine-api

# 4. Stop services
docker-compose down
```

**But you don't need Docker right now!** Use `start_api.bat` instead.

---

## 📁 Important Files

```
start_api.bat                    # ← Start your API (USE THIS!)
test/test_inference.py           # ← Test predictions
src/inference/metrics.py         # Prometheus metrics (auto-loaded)
src/monitoring/drift_detector.py # Drift detection
docker-compose.yml               # Docker config (optional)
MONITORING.md                    # Detailed guide (read later)
```

---

## 🆘 Troubleshooting

### API won't start?
```bash
# Check if model exists
dir artifacts\model_trainer\model.keras

# If not, run training first
python main.py
```

### Port 8000 already in use?
```bash
# Find what's using it
netstat -ano | findstr :8000

# Kill that process or change port in start_api.bat
```

### Test script fails?
```bash
# Make sure API is running first!
start_api.bat

# Then in another terminal:
uv run python test/test_inference.py
```

---

## 🎯 Next Steps (When You're Ready)

1. ✅ **Now:** Use `start_api.bat` to run locally
2. ⏳ **Later:** Read `MONITORING.md` for advanced features
3. ⏳ **Much Later:** Use Docker for production deployment

---

## 📚 Need More Help?

- **Quick questions:** Check `MONITORING.md`
- **API docs:** http://localhost:8000/docs (when API is running)
- **Metrics:** http://localhost:8000/metrics

---

**That's all you need to know! Just run `start_api.bat` and you're good to go! 🚀**
