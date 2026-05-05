from src.config.configuration import ConfigurationManager
from src.components.feature_engineering import FeatureEngineering
from src.logging.logger import logging
from src.exception.exception import CustomException
import sys

STAGE_NAME = "Feature Engineering Stage"


class FeatureEngineeringPipeline:
    def initiate_feature_engineering(self):
        config_manager = ConfigurationManager()
        config = config_manager.get_data_feature_engineering_config()
        fe = FeatureEngineering(config)
        logging.info(f"Feature Engineering config: {config}")
        fe.run()
        logging.info(f"Feature Engineering completed. Gold layer data saved at: {config.output_dir}")


if __name__ == "__main__":
    try:
        logging.info(f">>>>>> {STAGE_NAME} started <<<<<<")
        obj=FeatureEngineeringPipeline()
        obj.initiate_feature_engineering()
        logging.info(f">>>>>> {STAGE_NAME} completed <<<<<<\n")
    except Exception as e:
        logging.error(f"Error in stage {STAGE_NAME}")
        raise CustomException(e, sys)