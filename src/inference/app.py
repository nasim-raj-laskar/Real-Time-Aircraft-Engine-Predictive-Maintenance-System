from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from datetime import datetime, timezone
import time
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from src.inference.loader import load_artifacts
from src.inference.routes import router, init_router, _get_feature_store
from src.inference.predictor import InferenceError
from src.inference.ws import ws_router, init_ws
from src.inference.metrics import (
    prediction_latency_seconds,
    model_load_time_seconds,
    prediction_errors_total
)

app = FastAPI(
    title="Aircraft Engine RUL Prediction API",
    description="Real-time prediction of Remaining Useful Life for aircraft engines",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened per-origin once frontend domain is known
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(InferenceError)
async def inference_error_handler(request: Request, exc: InferenceError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Inference failed",
            "detail": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.middleware("http")
async def track_latency(request: Request, call_next):
    """Track request latency for predictions."""
    start_time = time.time()
    response = await call_next(request)
    latency = time.time() - start_time
    
    if request.url.path == "/predict":
        prediction_latency_seconds.observe(latency)
    
    return response


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.on_event("startup")
async def startup():
    start_time = time.time()
    model, scaler, config = load_artifacts()
    load_time = time.time() - start_time
    model_load_time_seconds.set(load_time)
    init_router(model, scaler, config)
    # Share the same feature store instance with the WS layer
    init_ws(model, scaler, config, _get_feature_store())
    print(f"✓ Model loaded in {load_time:.2f}s")


app.include_router(router)
app.include_router(ws_router)
