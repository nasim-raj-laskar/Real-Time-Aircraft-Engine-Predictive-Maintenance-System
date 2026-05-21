import joblib
import mlflow.tensorflow
from mlflow.tracking import MlflowClient
from pathlib import Path
from datetime import datetime, timezone
from src.utils.mlflow_setup import setup_mlflow
from src.utils.common import load_json
from src.config.configuration import ConfigurationManager


def load_artifacts() -> tuple:
    setup_mlflow()

    cfg = ConfigurationManager()
    registry_cfg = cfg.get_model_registry_config()
    transform_cfg = cfg.get_data_transformation_config()
    feature_cfg = cfg.get_data_feature_engineering_config()

    # Load model from MLflow registry
    client = MlflowClient()
    model_name = registry_cfg.registered_model_name
    stage = registry_cfg.stage

    versions = client.get_latest_versions(model_name, stages=[stage])
    if not versions:
        raise RuntimeError(f"No model found in stage '{stage}' for '{model_name}'")

    model_version = versions[0].version
    model_uri = f"models:/{model_name}/{stage}"
    model = mlflow.tensorflow.load_model(model_uri)
    print(f"✓ Model loaded from MLflow registry: {model_uri} (version {model_version})")

    # Pull trained_on timestamp from the MLflow run
    run_id = versions[0].run_id
    run = client.get_run(run_id)
    trained_on = datetime.fromtimestamp(run.info.start_time / 1000, tz=timezone.utc).isoformat()

    # Load scaler from path defined in config.yaml
    scaler = joblib.load(transform_cfg.scaler_path)
    print(f"✓ Scaler loaded from {transform_cfg.scaler_path}")

    # Load feature config if it exists, else build from yaml configs
    config_path = Path(feature_cfg.output_dir) / "feature_config.json"
    if config_path.exists():
        config = load_json(config_path)
        config = dict(config)
    else:
        config = {
            "window_size": feature_cfg.window_size,
            "features": transform_cfg.keep_sensors,
            "rul_clip": feature_cfg.rul_clip,
        }

    config["model_version"] = f"{model_name}_v{model_version}"
    config["trained_on"] = trained_on

    # add runtime redis config if present
    try:
        cfg_mgr = ConfigurationManager()
        redis_cfg = cfg_mgr.get_redis_config()
        if redis_cfg:
            config["redis"] = redis_cfg
    except Exception:
        # non-fatal; Redis config is optional
        pass

    return model, scaler, config
