from src.config.configuration import ConfigurationManager
from src.components.model_training import ModelTrainer
from src.logging.logger import logging
from src.exception.exception import CustomException
import sys

STAGE_NAME = "Model Training Stage"

class ModelTrainingPipeline:
    def initiate_model_training(self):
        config_manager = ConfigurationManager()
        model_trainer_config = (config_manager.get_model_trainer_config())
        trainer = ModelTrainer(config=model_trainer_config)
        logging.info(f"Model Trainer config: {model_trainer_config}")
        trainer.run()
        logging.info(f"Model training completed. Model and history saved at: {model_trainer_config.root_dir}")

if __name__ == "__main__":
    try:
        logging.info(f">>>>>> Stage {STAGE_NAME} started <<<<<<")
        obj = ModelTrainingPipeline()
        obj.initiate_model_training()
        logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n")
    except Exception as e:
        raise CustomException(e, sys)