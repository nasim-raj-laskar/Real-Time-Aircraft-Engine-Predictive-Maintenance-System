from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from pydantic import BaseModel, Field

@dataclass
class DataIngestionConfig:
    root_dir: Path
    s3_bucket: str
    s3_keys: Dict[str, str]
    local_data_dir: Path

@dataclass
class DataValidationConfig:
    root_dir: Path
    data_dir: Path
    status_file: Path
    expected_columns: int
    column_names: list

@dataclass
class DataTransformationConfig:
    root_dir: Path
    data_dir: Path
    processed_dir: Path
    s3_bucket: str
    s3_silver_prefix: str
    train_output: str
    test_output: str
    scaler_path: Path
    drop_columns: List[str]
    keep_sensors: List[str]
    rul_clip: int

@dataclass
class DataFeatureEngineeringConfig:
    root_dir: Path
    processed_dir: Path
    output_dir: Path
    s3_bucket: str
    s3_gold_prefix: str
    X_train: str
    y_train: str
    X_val: str
    y_val: str
    X_test: str
    y_test: str
    window_size: int
    test_size: float
    rul_clip: int
    random_state: int

@dataclass
class ModelTrainerConfig:
    root_dir: Path
    gold_dir: Path
    model_path: Path
    history_path: Path
    s3_bucket: str
    s3_artifact_prefix: str
    gru_units: List[int]
    dense_units: List[int]
    dropout_rates: List[float]
    l2_regularization: float
    epochs: int
    batch_size: int
    learning_rate: float
    early_stopping_patience: int
    reduce_lr_patience: int
    reduce_lr_factor: float
    min_lr: float

@dataclass
class ModelEvaluationConfig:
    root_dir: Path
    model_path: Path
    gold_dir: Path
    metrics_path: Path
    results_path: Path
    confusion_matrix_path: Path
    prediction_plot_path: Path
    error_distribution_path: Path
    s3_bucket: str
    s3_artifact_prefix: str

@dataclass
class ModelRegistryConfig:
    root_dir: Path
    model_path: Path
    gold_dir: Path
    metrics_path: Path
    registered_model_name: str
    rmse_threshold: float
    nasa_threshold: float
    stage: str
    s3_bucket: str
    s3_artifact_prefix: str

#INFERENCE
class SensorData(BaseModel):
    engine_id: str
    sensor_data: List[List[float]] = Field(..., description="30 timesteps × 11 sensor readings (normalized)")


class RawSensorData(BaseModel):
    engine_id: str
    sensor_data: List[Dict[str, float]] = Field(
        ...,
        description=(
            "30 timesteps of raw sensor readings. "
            "Each timestep must include all required feature keys."
        ),
        min_items=30,
        max_items=30,
    )


class SingleSensorReading(BaseModel):
    engine_id: str
    reading: Dict[str, float]


class PredictionResponse(BaseModel):
    engine_id: str
    remaining_cycles: int
    failure_risk: float
    risk_level: str
    confidence: float
    timestamp: str
    model_version: str
