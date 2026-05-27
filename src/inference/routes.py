import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

from src.entity.config_entity import RawSensorData, SensorData, PredictionResponse, SingleSensorReading
from src.inference.predictor import run_prediction, run_raw_prediction
from src.inference.buffer import EngineBuffer, InMemoryEngineBuffer
from src.inference.feature_store import RedisFeatureStore
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
_buffer = None
_feature_store: Optional[RedisFeatureStore] = None
# Cache of last prediction per engine_id: {engine_id: PredictionResponse}
_last_predictions: Dict[str, dict] = {}


def init_router(model, scaler, config: dict):
    global _model, _scaler, _config, _buffer, _feature_store
    _model, _scaler, _config = model, scaler, config
    window = int(config.get("window_size", 30))
    features = list(config.get("features", []))
    redis_cfg = config.get("redis") or {}
    import os
    redis_url = os.getenv("REDIS_URL") or redis_cfg.get("url") or config.get("redis_url") or "redis://localhost:6379/0"
    ttl = int(redis_cfg.get("ttl_seconds", redis_cfg.get("ttl", 3600)))
    # Rolling buffer (push/stream pathway)
    try:
        _buffer = EngineBuffer(window_size=window, sensor_cols=features, redis_url=redis_url, ttl_seconds=ttl)
    except Exception:
        _buffer = InMemoryEngineBuffer(window_size=window, sensor_cols=features)
    # Feature store (Flink streaming pathway) — lazy, retried on first use
    try:
        _feature_store = RedisFeatureStore(
            window_size=window,
            n_sensors=len(features),
            redis_url=redis_url,
            ttl_seconds=ttl,
        )
    except Exception as e:
        logger.warning(f"Feature store unavailable at startup (will retry on demand): {e}")
        _feature_store = None


def _get_feature_store() -> Optional[RedisFeatureStore]:
    """Return _feature_store, retrying connection if it failed at startup."""
    global _feature_store
    if _feature_store is not None:
        return _feature_store
    if _config is None:
        return None
    import os
    redis_cfg = _config.get("redis") or {}
    redis_url = os.getenv("REDIS_URL") or redis_cfg.get("url") or "redis://localhost:6379/0"
    ttl = int(redis_cfg.get("ttl_seconds", redis_cfg.get("ttl", 3600)))
    features = list(_config.get("features", []))
    try:
        _feature_store = RedisFeatureStore(
            window_size=int(_config.get("window_size", 30)),
            n_sensors=len(features),
            redis_url=redis_url,
            ttl_seconds=ttl,
        )
        logger.info("Feature store reconnected successfully")
    except Exception as e:
        logger.warning(f"Feature store reconnect failed: {e}")
    return _feature_store


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
        
        # Cache last prediction for fleet endpoints
        _last_predictions[data.engine_id] = {
            **result.model_dump(),
            "buffer_size": _buffer.size(data.engine_id) if _buffer else None,
        }

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

        # Cache last prediction for fleet endpoints
        _last_predictions[data.engine_id] = {
            **result.model_dump(),
            "buffer_size": _buffer.size(data.engine_id) if _buffer else None,
        }

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


@router.post("/push")
async def push_single(reading: SingleSensorReading):
    """Push a single raw sensor reading into the per-engine buffer.

    Body: {"engine_id": "ENG-1", "reading": {"s2":..., "s3":..., ...}}
    """
    _check_ready()
    try:
        _buffer.push(reading.engine_id, reading.reading)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"engine_id": reading.engine_id, "buffer_size": _buffer.size(reading.engine_id)}


@router.get("/predict/stream/{engine_id}", response_model=PredictionResponse)
async def predict_stream(engine_id: str):
    _check_ready()
    try:
        window = _buffer.get_window(engine_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    raw = RawSensorData(engine_id=engine_id, sensor_data=window)
    try:
        result = run_raw_prediction(raw, _model, _scaler, _config)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream prediction failed: {e}")

    return result


@router.get("/predict/engine/{engine_id}", response_model=PredictionResponse)
async def predict_from_feature_store(engine_id: str):
    """Run inference using the feature tensor written to Redis by the Flink pipeline.

    No request body needed — the (window_size, n_sensors) tensor is fetched
    directly from the Redis feature store key `engine:{id}:features`.
    Returns 404 if no features exist (engine not yet seen or TTL expired).
    """
    _check_ready()
    fs = _get_feature_store()
    if fs is None:
        raise HTTPException(status_code=503, detail="Feature store (Redis) is not available")

    window = fs.get_features(engine_id)
    if window is None:
        meta = _feature_store.get_meta(engine_id)
        detail = (
            f"No feature tensor found for engine '{engine_id}'. "
            "Has telemetry been received in the last hour?"
        )
        raise HTTPException(status_code=404, detail=detail)

    features = list(_config.get("features", []))
    sensor_data = [
        {features[j]: float(window[i, j]) for j in range(len(features))}
        for i in range(window.shape[0])
    ]
    raw = RawSensorData(engine_id=engine_id, sensor_data=sensor_data)
    try:
        result = run_raw_prediction(raw, _model, _scaler, _config)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feature store prediction failed: {e}")

    _last_predictions[engine_id] = {
        **result.model_dump(),
        "buffer_size": _buffer.size(engine_id) if _buffer else None,
    }
    prediction_requests_total.labels(engine_id=engine_id, risk_level=result.risk_level).inc()
    predicted_rul_cycles.observe(result.remaining_cycles)
    failure_risk_score.observe(result.failure_risk)
    prediction_confidence.observe(result.confidence)
    if result.risk_level == "CRITICAL":
        critical_engines_total.inc()

    return result


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


@router.get("/engines")
async def list_engines():
    """List all active engines — merges buffer engines and Redis feature store engines."""
    _check_ready()
    fs = _get_feature_store()
    engine_ids = set(_buffer.list_engines() if _buffer else [])
    if fs:
        engine_ids |= set(fs.list_active_engines())
    engines = []
    for eid in sorted(engine_ids):
        last = _last_predictions.get(eid)
        in_redis = fs.exists(eid) if fs else False
        buf_size = _buffer.size(eid) if _buffer else 0
        engines.append({
            "engine_id": eid,
            "source": "redis_stream" if in_redis else "push_buffer",
            "ready": in_redis or buf_size >= _config.get("window_size", 30),
            "last_prediction": last,
        })
    return {"engines": engines, "total": len(engines)}


@router.get("/engines/{engine_id}")
async def get_engine(engine_id: str):
    """Get status and last prediction for a specific engine."""
    _check_ready()
    fs = _get_feature_store()
    in_redis = fs.exists(engine_id) if fs else False
    buf_size = _buffer.size(engine_id) if _buffer else 0
    last = _last_predictions.get(engine_id)
    if not in_redis and buf_size == 0 and last is None:
        raise HTTPException(status_code=404, detail=f"Engine '{engine_id}' not found")
    return {
        "engine_id": engine_id,
        "source": "redis_stream" if in_redis else "push_buffer",
        "ready": in_redis or buf_size >= _config.get("window_size", 30),
        "last_prediction": last,
    }



@router.get("/alerts")
async def get_alerts(min_risk_level: Optional[str] = "HIGH"):
    """Return engines whose last prediction is at or above the given risk level.

    min_risk_level: LOW | MEDIUM | HIGH | CRITICAL  (default: HIGH)
    """
    _check_ready()
    rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    threshold = rank.get(min_risk_level.upper(), 2)
    alerts = [
        pred for pred in _last_predictions.values()
        if rank.get(pred.get("risk_level", "LOW"), 0) >= threshold
    ]
    alerts.sort(key=lambda x: x.get("failure_risk", 0), reverse=True)
    return {
        "alerts": alerts,
        "total": len(alerts),
        "min_risk_level": min_risk_level.upper(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


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


@router.get("/model/evaluation")
async def model_evaluation():
    """Return evaluation metrics from artifacts/model_evaluation/metrics.json."""
    import json
    metrics_path = Path("artifacts/model_evaluation/metrics.json")
    if not metrics_path.exists():
        raise HTTPException(status_code=404, detail="Evaluation metrics not found")
    with open(metrics_path) as f:
        data = json.load(f)
    cr = data.get("classification_report", {})
    critical = cr.get("Critical", {})
    weighted = cr.get("weighted avg", {})
    return {
        "rmse":               round(data.get("rmse", 0), 2),
        "nasa_score":         round(data.get("nasa_score", 0), 1),
        "precision_critical": round(critical.get("precision", 0), 3),
        "recall_critical":    round(critical.get("recall", 0), 3),
        "f1_critical":        round(critical.get("f1-score", 0), 3),
        "accuracy":           round(cr.get("accuracy", 0), 3),
        "f1_weighted":        round(weighted.get("f1-score", 0), 3),
    }
