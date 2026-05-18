from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from src.inference.loader import load_artifacts
from src.inference.routes import router, init_router
from src.inference.predictor import InferenceError

app = FastAPI(
    title="Aircraft Engine RUL Prediction API",
    description="Real-time prediction of Remaining Useful Life for aircraft engines",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # update when frontend is deployed
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


@app.on_event("startup")
async def startup():
    model, scaler, config = load_artifacts()
    init_router(model, config)


app.include_router(router)
