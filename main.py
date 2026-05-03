from src.logging.logger import logging
from src.exception.exception import CustomException
import sys
from src.pipeline.data_ingestion_pipeline import DataIngestionPipeline
from src.pipeline.data_validation_pipeline import DataValidationPipeline




STAGE_NAME = "Data Ingestion Stage"
try:
    logging.info(f">>>>>> Stage {STAGE_NAME} started <<<<<<")
    obj = DataIngestionPipeline()
    obj.initiate_data_ingestion()
    logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n\nx================x")
except Exception as e:
    logging.error(f"Error in stage {STAGE_NAME}")
    raise CustomException(e, sys)

STAGE_NAME = "Data Validation Stage"
try:
    logging.info(f">>>>>> Stage {STAGE_NAME} started <<<<<<")
    obj = DataValidationPipeline()
    obj.initiate_data_validation()
    logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n\nx================x")
except Exception as e:
    logging.error(f"Error in stage {STAGE_NAME}")
    raise CustomException(e, sys)