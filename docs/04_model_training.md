# Model Selection and Training

## Current Implementation

The project uses a **GRU (Gated Recurrent Unit)** model for RUL prediction. This is a deep learning approach that processes temporal sequences of sensor data.

## Prediction Target

The system predicts:

| Output | Type | Description |
|--------|------|-------------|
| RUL | Regression | Remaining flight cycles before failure (normalized to [0,1]) |

Failure risk can be derived from RUL: `risk = 1 - RUL`

```mermaid
graph TD
    A[Preprocessed Data] --> B[Sequence Building]
    
    B --> C[GRU Model]
    
    C --> D[Sequences<br/>30 x 11]
    
    D --> E[RUL Prediction<br/>Normalized 0-1]
    
    E --> F[Denormalize<br/>RUL * 125]
    
    F --> G[Derive Failure Risk]
    G --> H[risk = 1 - RUL/125]
    
    style C fill:#90EE90,stroke:#333,stroke-width:2px,color:#000
    style E fill:#FFD700,stroke:#333,stroke-width:2px,color:#000
```

---

## Model Architecture

The implemented model is a **multi-layer GRU** with the following architecture:

```python
Input: (batch_size, 30, 11)  # 30 timesteps, 11 sensors
│
GRU Layer 1: 128 units, return_sequences=True
Dropout: 0.3
│
GRU Layer 2: 64 units, return_sequences=False
Dropout: 0.3
│
Dense Layer 1: 32 units, ReLU, L2 regularization
Dense Layer 2: 16 units, ReLU, L2 regularization
│
Output: 1 unit, Sigmoid activation
│
Output: Normalized RUL in [0, 1]
```

### Key Configuration

```yaml
# From config/model.yaml
gru_units: [128, 64]
dense_units: [32, 16]
dropout_rates: [0.3, 0.3]
l2_regularization: 0.001
learning_rate: 0.001
batch_size: 256
epochs: 100
```

### Training Features

- **Sample Weighting**: Higher weight for samples near failure
  ```python
  sample_weights = 1.0 + 1.5 * y_train
  ```
- **Early Stopping**: Patience of 15 epochs on validation loss
- **Learning Rate Reduction**: Factor 0.5, patience 5 epochs
- **Optimizer**: Adam with initial LR 0.001

---

## Training Pipeline Implementation

The training is implemented in `src/components/model_training.py`:

```python
class ModelTrainer:
    def build_model(self, window_size, n_features):
        inp = tf.keras.Input(shape=(window_size, n_features))
        x = inp
        
        # GRU layers
        for i, units in enumerate(self.config.gru_units):
            return_sequences = i < len(self.config.gru_units) - 1
            x = layers.GRU(units, return_sequences=return_sequences)(x)
            x = layers.Dropout(self.config.dropout_rates[i])(x)
        
        # Dense layers
        for units in self.config.dense_units:
            x = layers.Dense(
                units, 
                activation='relu',
                kernel_regularizer=regularizers.l2(self.config.l2_regularization)
            )(x)
        
        # Output
        out = layers.Dense(1, activation='sigmoid')(x)
        
        model = models.Model(inp, out)
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=self.config.learning_rate),
            loss='mse',
            metrics=[tf.keras.metrics.RootMeanSquaredError(name='rmse')]
        )
        return model
```

---

## MLflow Integration

All training runs are logged to MLflow:

```python
with mlflow.start_run():
    # Log hyperparameters
    mlflow.log_params({
        "epochs": config.epochs,
        "batch_size": config.batch_size,
        "learning_rate": config.learning_rate,
        "gru_units": config.gru_units,
        "dense_units": config.dense_units,
        "dropout_rates": config.dropout_rates,
        "l2_regularization": config.l2_regularization,
        "window_size": window_size,
        "n_features": n_features,
    })
    
    # Train model
    history = model.fit(...)
    
    # Log metrics
    mlflow.log_metrics({
        "train_loss": history.history["loss"][-1],
        "train_rmse": history.history["rmse"][-1],
        "val_loss": history.history["val_loss"][-1],
        "val_rmse": history.history["val_rmse"][-1],
    })
    
    # Log artifacts
    mlflow.log_artifact("artifacts/model_trainer/history.json")
```

---

## Deriving Failure Risk from RUL

Failure risk is computed from the predicted RUL:

```python
RUL_CLIP = 125

def rul_to_risk(rul_pred: float) -> float:
    """Returns failure probability in [0, 1]."""
    return float(np.clip(1.0 - (rul_pred / RUL_CLIP), 0.0, 1.0))
```

Risk interpretation:
- `0.0 – 0.3` → Healthy, no action
- `0.3 – 0.6` → Monitor closely
- `0.6 – 0.8` → Schedule maintenance
- `0.8 – 1.0` → Imminent failure, ground aircraft

---

## Model Artifacts

After training, the following artifacts are saved:

```
artifacts/model_trainer/
├── model.keras              # Trained Keras model
└── history.json            # Training history (loss, metrics per epoch)

artifacts/data_feature_engineering/
└── feature_config.json     # Feature metadata (window_size, sensor list)

artifacts/data_transformation/
└── scaler.pkl              # MinMaxScaler for inference
```

All artifacts are also uploaded to S3 for versioning and deployment.

---

## Training Pipeline Execution

Run the complete pipeline:

```bash
python main.py
```

Or run training stage individually:

```python
from src.pipeline.model_trainer_pipeline import ModelTrainingPipeline

pipeline = ModelTrainingPipeline()
pipeline.initiate_model_training()
```

Note: Model training stage is currently commented out in `main.py` to allow running other stages independently.

---

## Training Pipeline Summary

```mermaid
flowchart TD
    A[Gold Layer<br/>X_train.npy, y_train.npy] --> B[Load Data]
    B --> C[Build GRU Model]
    C --> D[Configure Callbacks<br/>EarlyStopping, ReduceLR]
    
    D --> E[Train with Sample Weights]
    E --> F[MLflow Logging]
    
    F --> G[Save Model<br/>model.keras]
    F --> H[Save History<br/>history.json]
    
    G --> I[Upload to S3]
    H --> I
    
    I --> J[Model Registry]
    
    style A fill:#E8F4F8,stroke:#333,stroke-width:2px,color:#000
    style C fill:#FFD700,stroke:#333,stroke-width:2px,color:#000
    style F fill:#90EE90,stroke:#333,stroke-width:2px,color:#000
    style J fill:#90EE90,stroke:#333,stroke-width:2px,color:#000
```
