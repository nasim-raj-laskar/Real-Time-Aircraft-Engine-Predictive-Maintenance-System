@echo off
echo Starting Aircraft Engine Inference API...
echo.

REM Check if artifacts exist
if not exist "artifacts\model_trainer\model.keras" (
    echo ERROR: Model artifacts not found!
    echo Please run: python main.py
    exit /b 1
)

echo Starting FastAPI server on http://localhost:8000
echo.
echo Available endpoints:
echo   - POST http://localhost:8000/predict
echo   - GET  http://localhost:8000/health
echo   - GET  http://localhost:8000/model/info
echo   - GET  http://localhost:8000/metrics
echo.

uv run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
