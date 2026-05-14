from src.config.configuration import ConfigurationManager
from src.components.model_registry import ModelRegistry
from src.logging.logger import logging
from src.exception.exception import CustomException
import sys

STAGE_NAME = "Model Registry Stage"


class ModelRegistryPipeline:
    def initiate_model_registry(self):
        config_manager = ConfigurationManager()
        config = (config_manager.get_model_registry_config())
        registry = ModelRegistry(config=config)
        logging.info("Loading metrics for model registry...")
        registry.run()
        logging.info("Model registry process completed successfully.")


if __name__ == "__main__":
    try:
        logging.info(f">>>>>> Stage {STAGE_NAME} started <<<<<<")
        obj = ModelRegistryPipeline()
        obj.initiate_model_registry()
        logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n")

    except Exception as e:
        raise CustomException(e, sys)