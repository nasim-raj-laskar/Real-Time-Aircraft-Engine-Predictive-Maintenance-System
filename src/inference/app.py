from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.inference.loader import load_artifacts
from src.inference.routes import router, init_router

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


@app.on_event("startup")
async def startup():
    model, scaler, config = load_artifacts()
    init_router(model, config)


app.include_router(router)
