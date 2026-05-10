import os
import mlflow
import dagshub
from dotenv import load_dotenv

load_dotenv()

def setup_mlflow():
    dagshub.auth.add_app_token(os.environ["DAGSHUB_TOKEN"])
    dagshub.init(
        repo_owner=os.environ["DAGSHUB_USERNAME"],
        repo_name=os.environ["DAGSHUB_REPO_NAME"],
        mlflow=True,
    )
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment("aircraft-engine-rul")
