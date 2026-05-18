import time
from typing import List

from fastapi import APIRouter, HTTPException

from src.entity.config_entity import SensorData, PredictionResponse
from src.inference.predictor import run_prediction

router = APIRouter()
_start_time = time.time()

_model = None
_config = None


def init_router(model, config: dict):
    global _model, _config
    _model, _config = model, config


def _check_ready():
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")


@router.post("/predict", response_model=PredictionResponse)
async def predict(data: SensorData):
    _check_ready()
    try:
        return run_prediction(data, _model, _config)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


@router.post("/predict/batch")
async def predict_batch(data: List[SensorData]):
    _check_ready()
    results = []
    for item in data:
        try:
            results.append(run_prediction(item, _model, _config).model_dump())
        except Exception as e:
            results.append({"engine_id": item.engine_id, "error": str(e)})
    return {"predictions": results, "total": len(results)}


@router.get("/health")
async def health():
    return {
        "status": "healthy" if _model is not None else "unhealthy",
        "model_loaded": _model is not None,
        "model_version": _config.get("model_version", "unknown") if _config else "unknown",
        "uptime_seconds": int(time.time() - _start_time),
    }


@router.get("/model/info")
async def model_info():
    if _config is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {
        "model_type": "GRU",
        "input_shape": [_config.get("window_size", 30), len(_config.get("features", []))],
        "window_size": _config.get("window_size", 30),
        "sensors": _config.get("features", []),
        "rul_clip": _config.get("rul_clip", 125),
        "model_version": _config.get("model_version", "unknown"),
        "trained_on": _config.get("trained_on", "unknown"),
    }
