"""
WebSocket endpoints for real-time streaming to the frontend.

/ws/telemetry   — engine metadata (cycle, event_time) for all active engines
/ws/predictions — RUL predictions for all active engines
/ws/alerts      — HIGH + CRITICAL engines only

All three poll Redis every `interval` seconds and broadcast to every
connected client. The frontend connects once and receives a continuous
stream of JSON messages without polling.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from src.inference.feature_store import RedisFeatureStore
from src.inference.predictor import run_raw_prediction
from src.entity.config_entity import RawSensorData

ws_router = APIRouter()

# Injected by init_ws() at startup — same objects used by the REST routes
_model = None
_scaler = None
_config: Optional[dict] = None
_feature_store: Optional[RedisFeatureStore] = None

TELEMETRY_INTERVAL = float(os.getenv("WS_TELEMETRY_INTERVAL", "2"))    # seconds
PREDICTION_INTERVAL = float(os.getenv("WS_PREDICTION_INTERVAL", "5"))  # seconds
ALERTS_INTERVAL = float(os.getenv("WS_ALERTS_INTERVAL", "5"))          # seconds

RISK_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def init_ws(model, scaler, config: dict, feature_store: RedisFeatureStore):
    global _model, _scaler, _config, _feature_store
    _model, _scaler, _config, _feature_store = model, scaler, config, feature_store


# ── helpers ───────────────────────────────────────────────────────────────────

def _predict_engine(engine_id: str) -> Optional[dict]:
    """Run inference for one engine from its Redis feature tensor. Returns None on any error."""
    if _feature_store is None or _model is None:
        return None
    window = _feature_store.get_features(engine_id)
    if window is None:
        return None
    features = list(_config.get("features", []))
    sensor_data = [
        {features[j]: float(window[i, j]) for j in range(len(features))}
        for i in range(window.shape[0])
    ]
    try:
        result = run_raw_prediction(
            RawSensorData(engine_id=engine_id, sensor_data=sensor_data),
            _model, _scaler, _config,
        )
        return result.model_dump()
    except Exception:
        return None


async def _send(ws: WebSocket, payload: dict):
    await ws.send_text(json.dumps(payload))


# ── /ws/telemetry ─────────────────────────────────────────────────────────────

@ws_router.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    """
    Streams engine metadata for all active engines every TELEMETRY_INTERVAL seconds.

    Message format:
        {
            "type": "telemetry",
            "timestamp": "...",
            "engines": [
                {"engine_id": "ENG-1", "cycle": 187, "event_time_ms": 1234567890},
                ...
            ],
            "total": 100
        }
    """
    await websocket.accept()
    try:
        while True:
            if _feature_store is None:
                await _send(websocket, {"type": "error", "detail": "Feature store not available"})
                await asyncio.sleep(TELEMETRY_INTERVAL)
                continue

            engine_ids = _feature_store.list_active_engines()
            engines = []
            for eid in sorted(engine_ids):
                meta = _feature_store.get_meta(eid)
                engines.append({
                    "engine_id": eid,
                    "cycle": int(meta.get("cycle", 0)) if meta else 0,
                    "event_time_ms": int(meta.get("event_time", 0)) if meta else 0,
                    "window_size": int(meta.get("window_size", 30)) if meta else 30,
                })

            await _send(websocket, {
                "type": "telemetry",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "engines": engines,
                "total": len(engines),
            })
            await asyncio.sleep(TELEMETRY_INTERVAL)

    except WebSocketDisconnect:
        pass


# ── /ws/predictions ───────────────────────────────────────────────────────────

@ws_router.websocket("/ws/predictions")
async def ws_predictions(websocket: WebSocket):
    """
    Runs inference on all active engines and streams results every PREDICTION_INTERVAL seconds.

    Message format:
        {
            "type": "predictions",
            "timestamp": "...",
            "predictions": [ <PredictionResponse>, ... ],
            "total": 100
        }
    """
    await websocket.accept()
    try:
        while True:
            if _feature_store is None or _model is None:
                await _send(websocket, {"type": "error", "detail": "Service not ready"})
                await asyncio.sleep(PREDICTION_INTERVAL)
                continue

            engine_ids = _feature_store.list_active_engines()
            predictions = []
            for eid in engine_ids:
                result = _predict_engine(eid)
                if result:
                    predictions.append(result)

            # Sort by failure_risk descending so frontend gets critical engines first
            predictions.sort(key=lambda x: x.get("failure_risk", 0), reverse=True)

            await _send(websocket, {
                "type": "predictions",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "predictions": predictions,
                "total": len(predictions),
            })
            await asyncio.sleep(PREDICTION_INTERVAL)

    except WebSocketDisconnect:
        pass


# ── /ws/alerts ────────────────────────────────────────────────────────────────

@ws_router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """
    Streams only HIGH and CRITICAL engines every ALERTS_INTERVAL seconds.

    Query param: ?min_risk=HIGH (default) or ?min_risk=CRITICAL

    Message format:
        {
            "type": "alerts",
            "timestamp": "...",
            "alerts": [ <PredictionResponse>, ... ],
            "total": 5,
            "min_risk_level": "HIGH"
        }
    """
    await websocket.accept()

    # Read query param from the WS handshake URL
    min_risk = websocket.query_params.get("min_risk", "HIGH").upper()
    threshold = RISK_RANK.get(min_risk, 2)

    try:
        while True:
            if _feature_store is None or _model is None:
                await _send(websocket, {"type": "error", "detail": "Service not ready"})
                await asyncio.sleep(ALERTS_INTERVAL)
                continue

            engine_ids = _feature_store.list_active_engines()
            alerts = []
            for eid in engine_ids:
                result = _predict_engine(eid)
                if result and RISK_RANK.get(result.get("risk_level", "LOW"), 0) >= threshold:
                    alerts.append(result)

            alerts.sort(key=lambda x: x.get("failure_risk", 0), reverse=True)

            await _send(websocket, {
                "type": "alerts",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "alerts": alerts,
                "total": len(alerts),
                "min_risk_level": min_risk,
            })
            await asyncio.sleep(ALERTS_INTERVAL)

    except WebSocketDisconnect:
        pass
