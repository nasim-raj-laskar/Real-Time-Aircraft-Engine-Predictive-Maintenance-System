"""
Export MinMaxScaler parameters from training artifacts to the Flink streaming pipeline.

Outputs:
  streaming/src/main/resources/scaler_params.csv
      Row 0: comma-separated min values  (one per sensor, in feature order)
      Row 1: comma-separated max values

  streaming/src/main/resources/pipeline_config.json
      Full metadata: sensor names, window_size, rul_clip, scaler stats.
      Single source of truth for the Java Flink project.

Run after every training run that produces a new scaler:
    uv run python scripts/export_scaler_params.py
"""

import json
import joblib
import numpy as np
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

SCALER_PATH = Path("artifacts/data_transformation/scaler.pkl")
FEATURE_CONFIG_PATH = Path("artifacts/data_feature_engineering/feature_config.json")
OUT_DIR = Path("streaming/src/main/resources")
CSV_OUT = OUT_DIR / "scaler_params.csv"
JSON_OUT = OUT_DIR / "pipeline_config.json"


def main():
    # ── Load artifacts ────────────────────────────────────────────────────────
    if not SCALER_PATH.exists():
        raise FileNotFoundError(
            f"Scaler not found at {SCALER_PATH}. Run the training pipeline first."
        )
    if not FEATURE_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Feature config not found at {FEATURE_CONFIG_PATH}. Run the training pipeline first."
        )

    scaler = joblib.load(SCALER_PATH)
    with open(FEATURE_CONFIG_PATH) as f:
        feature_config = json.load(f)

    sensors: list = feature_config["features"]
    window_size: int = feature_config["window_size"]
    rul_clip: int = feature_config["rul_clip"]

    data_min: np.ndarray = scaler.data_min_
    data_max: np.ndarray = scaler.data_max_

    if len(data_min) != len(sensors):
        raise ValueError(
            f"Scaler has {len(data_min)} features but feature_config lists {len(sensors)} sensors. "
            "Re-run the training pipeline to regenerate consistent artifacts."
        )

    # ── Export CSV ────────────────────────────────────────────────────────────
    # Format: 8 decimal places — sufficient precision for float32 inference
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    min_row = ",".join(f"{v:.8f}" for v in data_min)
    max_row = ",".join(f"{v:.8f}" for v in data_max)

    with open(CSV_OUT, "w") as f:
        f.write(min_row + "\n")
        f.write(max_row + "\n")

    print(f"✓ scaler_params.csv  →  {CSV_OUT}")
    print(f"  Sensors ({len(sensors)}): {', '.join(sensors)}")
    print(f"  Min: {[round(v, 4) for v in data_min]}")
    print(f"  Max: {[round(v, 4) for v in data_max]}")

    # ── Export JSON sidecar ───────────────────────────────────────────────────
    pipeline_config = {
        "sensors": sensors,
        "n_sensors": len(sensors),
        "window_size": window_size,
        "rul_clip": rul_clip,
        "scaler": {
            "type": "MinMaxScaler",
            "feature_range": list(scaler.feature_range),
            "data_min": data_min.tolist(),
            "data_max": data_max.tolist(),
            "data_range": (data_max - data_min).tolist(),
        },
        # Redis key schema shared by RedisSink (Flink) and RedisFeatureStore (FastAPI)
        "redis_key_schema": {
            "features": "engine:{engine_id}:features",
            "meta":     "engine:{engine_id}:meta",
            "buffer":   "engine:{engine_id}:buffer",
        },
    }

    with open(JSON_OUT, "w") as f:
        json.dump(pipeline_config, f, indent=2)

    print(f"✓ pipeline_config.json  →  {JSON_OUT}")
    print(f"  window_size={window_size}, rul_clip={rul_clip}, n_sensors={len(sensors)}")


if __name__ == "__main__":
    main()
