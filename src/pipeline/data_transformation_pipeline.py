from src.config.configuration import ConfigurationManager
from src.components.data_transformation import DataTransformation
from src.logging.logger import logging
from src.exception.exception import CustomException
import sys

STAGE_NAME = "Data Transformation Stage"


class DataTransformationPipeline:
    def initiate_data_transformation(self):
        config_manager = ConfigurationManager()
        config = config_manager.get_data_transformation_config()
        transformation = DataTransformation(config)
        logging.info(f"Data Transformation config: {config}")
        transformation.run()
        logging.info(f"Data Transformation completed. Processed data saved at: {config.processed_dir}")


if __name__ == "__main__":
    try:
        logging.info(f">>>>>> {STAGE_NAME} started <<<<<<")
        obj=DataTransformationPipeline()
        obj.initiate_data_transformation()
        logging.info(f">>>>>> {STAGE_NAME} completed <<<<<<\n")
    except Exception as e:
        logging.error(f"Error in stage {STAGE_NAME}")
        raise CustomException(e, sys)