#MAIN FILE
from src.logging.logger import logging
from src.exception.exception import CustomException
import sys
from src.pipeline.data_ingestion_pipeline import DataIngestionPipeline
from src.pipeline.data_validation_pipeline import DataValidationPipeline
from src.pipeline.data_transformation_pipeline import DataTransformationPipeline
from src.pipeline.feature_engineering_pipeline import FeatureEngineeringPipeline
from src.pipeline.model_trainer_pipeline import ModelTrainingPipeline
from src.pipeline.model_evaluation_pipeline import ModelEvaluationPipeline

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
    logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n")
except Exception as e:
    logging.error(f"Error in stage {STAGE_NAME}")
    raise CustomException(e, sys)

STAGE_NAME = "Data Transformation Stage"
try:
    logging.info(f">>>>>> Stage {STAGE_NAME} started <<<<<<")
    obj=DataTransformationPipeline()
    obj.initiate_data_transformation()
    logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n")
except Exception as e:
    logging.error(f"Error in stage {STAGE_NAME}")
    raise CustomException(e, sys)

STAGE_NAME = "Feature Engineering Stage"
try:
    logging.info(">>>>>> Stage Feature Engineering started <<<<<<")
    obj=FeatureEngineeringPipeline()
    obj.initiate_feature_engineering()
    logging.info(">>>>>> Stage Feature Engineering completed <<<<<<\n")
except Exception as e:
    logging.error(f"Error in stage {STAGE_NAME}")
    raise CustomException(e, sys)

STAGE_NAME = "Model Training Stage"
try:
    logging.info(f">>>>>> Stage {STAGE_NAME} started <<<<<<")
    obj = ModelTrainingPipeline()
    obj.initiate_model_training()
    logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n")
except Exception as e:
    logging.error(f"Error in stage {STAGE_NAME}")
    raise CustomException(e, sys)

STAGE_NAME = "Model Evaluation Stage"
try:
    logging.info(f">>>>>> Stage {STAGE_NAME} started <<<<<<")
    obj = ModelEvaluationPipeline()
    obj.initiate_model_evaluation()
    logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n")
except Exception as e:
    logging.error(f"Error in stage {STAGE_NAME}")
    raise CustomException(e, sys)