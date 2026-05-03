from src.config.configuration import ConfigurationManager
from src.components.data_validation import DataValidation
from src.logging.logger import logging
from src.exception.exception import CustomException
import sys

STAGE_NAME = "Data Validation Stage"


class DataValidationPipeline:
    def __init__(self):
        pass

    def initiate_data_validation(self):
        config_manager = ConfigurationManager()
        validation_config = config_manager.get_data_validation_config()
        validation = DataValidation(config=validation_config)
        logging.info(f"Data Validation config: {validation_config}")
        validation.run()
        logging.info(f"Data Validation completed with status file: {validation_config.status_file}")


if __name__ == "__main__":
    try:
        logging.info(f">>>>>> Stage {STAGE_NAME} started <<<<<<")
        obj = DataValidationPipeline()
        obj.initiate_data_validation()
        logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n\nx================x")
    except Exception as e:
        logging.error(f"Error in stage {STAGE_NAME}")
        raise CustomException(e, sys)