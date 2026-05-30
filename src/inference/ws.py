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
from functools import partial

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from src.inference.feature_store import RedisFeatureStore
from src.inference.metrics import (
    prediction_requests_total,
    predicted_rul_cycles,
    failure_risk_score,
    critical_engines_total,
    prediction_confidence,
    prediction_latency_seconds,
    active_engines,
)

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

def _predict_all_engines(engine_ids: list) -> list:
    """Single batched TF forward pass for all engines — O(1) instead of O(n)."""
    if _feature_store is None or _model is None:
        return []

    windows, valid_ids = [], []
    for eid in engine_ids:
        w = _feature_store.get_features(eid)
        if w is not None:
            windows.append(w)
            valid_ids.append(eid)

    if not windows:
        active_engines.set(0)
        return []

    import numpy as np
    import time as _time
    X = np.stack(windows, axis=0).astype(np.float32)  # (N, 30, 11)
    t0 = _time.perf_counter()
    preds = _model(X, training=False).numpy()[:, 0]   # (N,)
    prediction_latency_seconds.observe(_time.perf_counter() - t0)

    rul_clip = _config.get("rul_clip", 125)
    results = []
    now = datetime.now(timezone.utc).isoformat()
    version = _config.get("model_version", "unknown")

    active_engines.set(len(valid_ids))

    for eid, rul_norm in zip(valid_ids, preds):
        rul = max(0.0, float(rul_norm) * rul_clip)
        risk = round(max(0.0, min(1.0, 1.0 - (rul / rul_clip))), 3)
        if risk >= 0.8:   risk_level = "CRITICAL"
        elif risk >= 0.6: risk_level = "HIGH"
        elif risk >= 0.3: risk_level = "MEDIUM"
        else:             risk_level = "LOW"

        prediction_requests_total.labels(engine_id=eid, risk_level=risk_level).inc()
        predicted_rul_cycles.observe(rul)
        failure_risk_score.observe(risk)
        prediction_confidence.observe(1.0)
        if risk_level == "CRITICAL":
            critical_engines_total.inc()

        results.append({
            "engine_id": eid,
            "remaining_cycles": int(round(rul)),
            "failure_risk": risk,
            "risk_level": risk_level,
            "confidence": 1.0,
            "timestamp": now,
            "model_version": version,
        })
    return results


async def _send(ws: WebSocket, payload: dict):
    await ws.send_text(json.dumps(payload))


async def _run_batch_async(engine_ids: list) -> list:
    """Run _predict_all_engines in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_predict_all_engines, engine_ids))


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
            predictions = await _run_batch_async(engine_ids)

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
            all_results = await _run_batch_async(engine_ids)
            alerts = [
                r for r in all_results
                if RISK_RANK.get(r.get("risk_level", "LOW"), 0) >= threshold
            ]

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
