from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import tensorflow as tf
import numpy as np
import joblib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union

app = FastAPI(
    title="Aircraft Engine RUL Prediction API",
    description="Real-time prediction of Remaining Useful Life for aircraft engines",
    version="1.0.0",
)

model = None
scaler = None
config = None
start_time = time.time()

SENSOR_COLS = ["s2", "s3", "s4", "s7", "s9", "s11", "s12", "s14", "s17", "s20", "s21"]


class SensorData(BaseModel):
    engine_id: str
    sensor_data: List[List[float]] = Field(..., description="30 timesteps × 11 sensor readings (normalized)")


class PredictionResponse(BaseModel):
    engine_id: str
    remaining_cycles: int
    failure_risk: float
    risk_level: str
    confidence: float
    timestamp: str
    model_version: str


@app.on_event("startup")
async def load_artifacts():
    global model, scaler, config

    model_path = Path("artifacts/model_trainer/model.keras")
    scaler_path = Path("artifacts/data_transformation/scaler.pkl")
    config_path = Path("artifacts/data_feature_engineering/feature_config.json")

    if not model_path.exists():
        raise RuntimeError(f"Model not found at {model_path}")
    if not scaler_path.exists():
        raise RuntimeError(f"Scaler not found at {scaler_path}")

    model = tf.keras.models.load_model(model_path)
    scaler = joblib.load(scaler_path)

    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    else:
        config = {"window_size": 30, "features": SENSOR_COLS, "rul_clip": 125}

    print(f"✓ Model loaded from {model_path}")
    print(f"✓ Scaler loaded from {scaler_path}")


def _run_prediction(data: SensorData) -> PredictionResponse:
    sensor_array = np.array(data.sensor_data, dtype=np.float32)
    if sensor_array.shape != (30, 11):
        raise HTTPException(status_code=400, detail=f"Expected shape (30, 11), got {sensor_array.shape}")

    X = sensor_array.reshape(1, 30, 11)
    rul_normalized = float(model.predict(X, verbose=0)[0][0])

    rul_clip = config.get("rul_clip", 125)
    rul_pred = max(0.0, rul_normalized * rul_clip)
    risk = max(0.0, min(1.0, 1.0 - (rul_pred / rul_clip)))

    if risk >= 0.8:
        risk_level = "CRITICAL"
    elif risk >= 0.6:
        risk_level = "HIGH"
    elif risk >= 0.3:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return PredictionResponse(
        engine_id=data.engine_id,
        remaining_cycles=int(round(rul_pred)),
        failure_risk=round(risk, 3),
        risk_level=risk_level,
        confidence=0.85,
        timestamp=datetime.now(timezone.utc).isoformat(),
        model_version="gru_fd001_v1",
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict(data: SensorData):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    try:
        return _run_prediction(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


@app.post("/predict/batch")
async def predict_batch(data: List[SensorData]):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    results = []
    for item in data:
        try:
            results.append(_run_prediction(item).model_dump())
        except Exception as e:
            results.append({"engine_id": item.engine_id, "error": str(e)})

    return {"predictions": results, "total": len(results)}


@app.get("/health")
async def health():
    return {
        "status": "healthy" if model is not None else "unhealthy",
        "model_loaded": model is not None,
        "model_version": "gru_fd001_v1",
        "uptime_seconds": int(time.time() - start_time),
    }


@app.get("/model/info")
async def model_info():
    if config is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {
        "model_type": "GRU",
        "input_shape": [config.get("window_size", 30), len(config.get("features", SENSOR_COLS))],
        "window_size": config.get("window_size", 30),
        "sensors": config.get("features", SENSOR_COLS),
        "rul_clip": config.get("rul_clip", 125),
    }
