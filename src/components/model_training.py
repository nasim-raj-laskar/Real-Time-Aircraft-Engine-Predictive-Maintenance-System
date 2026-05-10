import numpy as np
import tensorflow as tf  #type: ignore
from tensorflow.keras import layers, models, regularizers  #type: ignore
from pathlib import Path
import mlflow

from src.entity.config_entity import ModelTrainerConfig
from src.logging.logger import logging
from src.utils.common import save_json, load_json
from src.utils.mlflow_setup import setup_mlflow
from src.metrics.plot import log_training_curves
from src.cloud.s3 import S3Client


class ModelTrainer:
    def __init__(self, config: ModelTrainerConfig):
        self.config = config
        self.s3 = S3Client()

    #LOAD DATA
    def load_data(self):
        logging.info("Loading Gold layer tensors...")

        gold_dir = self.config.gold_dir

        X_train = np.load(gold_dir / "X_train.npy")
        # amazonq-ignore-next-line
        y_train = np.load(gold_dir / "y_train.npy")

        X_val = np.load(gold_dir / "X_val.npy")
      
        # amazonq-ignore-next-line
        y_val = np.load(gold_dir / "y_val.npy")

        logging.info(f"X_train: {X_train.shape}")
        logging.info(f"X_val: {X_val.shape}")

        # amazonq-ignore-next-line
        return X_train, y_train, X_val, y_val

    #BUILD MODEL 
    def build_model(self, window_size, n_features):

        logging.info("Building GRU model...")

        inp = tf.keras.Input(shape=(window_size, n_features))

        x = inp

        for i, units in enumerate(self.config.gru_units):

            return_sequences = i < len(self.config.gru_units) - 1
            x = layers.GRU(units,return_sequences=return_sequences)(x)
            x = layers.Dropout(self.config.dropout_rates[i])(x)

        for units in self.config.dense_units:
            x = layers.Dense(units,
                activation='relu',
                kernel_regularizer=regularizers.l2(
                    self.config.l2_regularization
                )
            )(x)

        out = layers.Dense(1, activation='sigmoid')(x)

        model = models.Model(inp, out)

        model.compile(
            optimizer=tf.keras.optimizers.Adam(
                learning_rate=self.config.learning_rate
            ),
            loss='mse',
            metrics=[
                tf.keras.metrics.RootMeanSquaredError(name='rmse')
            ]
        )

        logging.info("Model compiled successfully")

        return model

    #CALLBACKS 
    def get_callbacks(self):

        logging.info("Creating callbacks...")

        callbacks = [

            tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=self.config.early_stopping_patience,
                restore_best_weights=True,
                verbose=1
            ),

            tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=self.config.reduce_lr_factor,
                patience=self.config.reduce_lr_patience,
                min_lr=self.config.min_lr,
                verbose=1
            )
        ]

        return callbacks

    # TRAIN 
    def train(self):

        setup_mlflow()

        X_train, y_train, X_val, y_val = self.load_data()

        window_size = X_train.shape[1]
        n_features = X_train.shape[2]

        model = self.build_model(window_size, n_features)

        sample_weights = (
            1.0 + 1.5 * y_train
        ).astype(np.float32)

        logging.info("Starting model training...")

        with mlflow.start_run():

            mlflow.log_params({
                "epochs": self.config.epochs,
                "batch_size": self.config.batch_size,
                "learning_rate": self.config.learning_rate,
                "gru_units": self.config.gru_units,
                "dense_units": self.config.dense_units,
                "dropout_rates": self.config.dropout_rates,
                "l2_regularization": self.config.l2_regularization,
                "window_size": window_size,
                "n_features": n_features,
            })

            history = model.fit(
                X_train,
                y_train,
                validation_data=(X_val, y_val),
                epochs=self.config.epochs,
                batch_size=self.config.batch_size,
                sample_weight=sample_weights,
                callbacks=self.get_callbacks(),
                verbose=1
            )

            logging.info("Training completed")

            # LOG METRICS
            final_epoch = len(history.history["loss"]) - 1
            mlflow.log_metrics({
                "train_loss": history.history["loss"][final_epoch],
                "train_rmse": history.history["rmse"][final_epoch],
                "val_loss": history.history["val_loss"][final_epoch],
                "val_rmse": history.history["val_rmse"][final_epoch],
            })

            #  SAVE MODEL 
            model.save(self.config.model_path)
            logging.info(f"Model saved at: {self.config.model_path}")

            #  SAVE HISTORY 
            save_json(self.config.history_path, history.history)
            logging.info(f"Training history saved at: {self.config.history_path}")

            # LOG HISTORY ARTIFACT
            mlflow.log_artifact(str(self.config.history_path), artifact_path="artifacts")
            logging.info("history.json logged to MLflow")

            # LOG TRAINING CURVES
            log_training_curves(history.history)
            logging.info("Training curves logged to MLflow")

        #  UPLOAD ARTIFACTS 
        logging.info("Uploading model artifacts to S3...")

        self.s3.upload(self.config.model_path, self.config.s3_bucket,
                       f"{self.config.s3_artifact_prefix}model.keras")

        self.s3.upload(self.config.history_path, self.config.s3_bucket,
                       f"{self.config.s3_artifact_prefix}history.json")

        logging.info("Artifacts uploaded successfully")

    #  RUN 
    def run(self):

        logging.info("========== MODEL TRAINING STARTED ==========")
        self.train()
        logging.info("========== MODEL TRAINING COMPLETED ==========\n")