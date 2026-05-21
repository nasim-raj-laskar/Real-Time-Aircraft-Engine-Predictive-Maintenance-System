import time
from typing import List

from fastapi import APIRouter, HTTPException

from src.entity.config_entity import RawSensorData, SensorData, PredictionResponse
from src.inference.predictor import run_prediction, run_raw_prediction
from src.inference.metrics import (
    prediction_requests_total,
    predicted_rul_cycles,
    failure_risk_score,
    critical_engines_total,
    prediction_confidence,
    prediction_errors_total
)
from src.inference.structured_logger import setup_inference_logger
from pathlib import Path

logger = setup_inference_logger('inference', Path('logs/inference.log'))

router = APIRouter()
_start_time = time.time()

_model = None
_scaler = None
_config = None


def init_router(model, scaler, config: dict):
    global _model, _scaler, _config
    _model, _scaler, _config = model, scaler, config


def _check_ready():
    if _model is None or _scaler is None:
        raise HTTPException(status_code=503, detail="Inference service not fully initialized")


@router.post("/predict", response_model=PredictionResponse)
async def predict(data: SensorData):
    _check_ready()
    start_time = time.time()
    
    try:
        result = run_prediction(data, _model, _config)
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Record metrics
        prediction_requests_total.labels(
            engine_id=data.engine_id,
            risk_level=result.risk_level
        ).inc()
        
        predicted_rul_cycles.observe(result.remaining_cycles)
        failure_risk_score.observe(result.failure_risk)
        prediction_confidence.observe(result.confidence)
        
        if result.risk_level == 'CRITICAL':
            critical_engines_total.inc()
        
        # Log prediction
        logger.info(
            "Prediction completed",
            extra={
                'engine_id': data.engine_id,
                'rul': result.remaining_cycles,
                'risk': result.failure_risk,
                'risk_level': result.risk_level,
                'confidence': result.confidence,
                'latency_ms': round(latency_ms, 2)
            }
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        prediction_errors_total.labels(error_type=type(e).__name__).inc()
        logger.error(
            f"Prediction failed: {e}",
            extra={'engine_id': data.engine_id}
        )
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")


@router.post("/predict/raw", response_model=PredictionResponse)
async def predict_raw(data: RawSensorData):
    _check_ready()
    start_time = time.time()
    try:
        result = run_raw_prediction(data, _model, _scaler, _config)
        latency_ms = (time.time() - start_time) * 1000

        prediction_requests_total.labels(
            engine_id=data.engine_id,
            risk_level=result.risk_level
        ).inc()
        predicted_rul_cycles.observe(result.remaining_cycles)
        failure_risk_score.observe(result.failure_risk)
        prediction_confidence.observe(result.confidence)

        if result.risk_level == 'CRITICAL':
            critical_engines_total.inc()

        logger.info(
            "Raw prediction completed",
            extra={
                'engine_id': data.engine_id,
                'rul': result.remaining_cycles,
                'risk': result.failure_risk,
                'risk_level': result.risk_level,
                'confidence': result.confidence,
                'latency_ms': round(latency_ms, 2)
            }
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        prediction_errors_total.labels(error_type=type(e).__name__).inc()
        logger.error(
            f"Raw prediction failed: {e}",
            extra={'engine_id': data.engine_id}
        )
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
