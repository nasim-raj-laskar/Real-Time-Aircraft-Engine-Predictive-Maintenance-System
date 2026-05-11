from src.config.configuration import ConfigurationManager
from src.components.model_evaluation import ModelEvaluation
from src.logging.logger import logging
from src.exception.exception import CustomException
import sys

STAGE_NAME = "Model Evaluation Stage"


class ModelEvaluationPipeline:
    def initiate_model_evaluation(self):
        config_manager = ConfigurationManager()
        evaluation_config = (config_manager.get_model_evaluation_config())
        evaluation = ModelEvaluation(config=evaluation_config)
        logging.info(f"Model Evaluation config: {evaluation_config}")
        evaluation.run()
        logging.info(f"Model Evaluation completed. Results saved at: {evaluation_config.results_path}")


if __name__ == "__main__":
    try:
        logging.info(f">>>>>> Stage {STAGE_NAME} started <<<<<<")
        obj = ModelEvaluationPipeline()
        obj.initiate_model_evaluation()
        logging.info(f">>>>>> Stage {STAGE_NAME} completed <<<<<<\n")
    except Exception as e:
        raise CustomException(e, sys)