import numpy as np
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from src.entity.config_entity import SensorData, PredictionResponse

MC_SAMPLES = 30


class InferenceError(Exception):
    pass


def _mc_predict(model, X: np.ndarray) -> tuple[float, float]:
    """Run MC Dropout inference. Returns (mean_rul_normalized, confidence)."""
    preds = np.array(
        [model(X, training=True).numpy()[0][0] for _ in range(MC_SAMPLES)]
    )
    mean = float(preds.mean())
    std = float(preds.std())
    # Normalize std to [0,1] range and invert to get confidence
    confidence = float(round(max(0.0, min(1.0, 1.0 - std * 10)), 3))
    return mean, confidence


def run_prediction(data: SensorData, model, config: dict) -> PredictionResponse:
    sensor_array = np.array(data.sensor_data, dtype=np.float32)

    window_size = config.get("window_size", 30)
    n_features = len(config.get("features", []))

    if sensor_array.shape != (window_size, n_features):
        raise HTTPException(
            status_code=400,
            detail=f"Expected shape ({window_size}, {n_features}), got {sensor_array.shape}"
        )

    X = sensor_array.reshape(1, window_size, n_features)
    try:
        rul_normalized, confidence = _mc_predict(model, X)
    except Exception as e:
        raise InferenceError(f"Model inference failed: {e}")

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
        confidence=confidence,
        timestamp=datetime.now(timezone.utc).isoformat(),
        model_version=config.get("model_version", "unknown"),
    )
