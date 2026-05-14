""
import os
import warnings
import logging

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=info, 2=warning, 3=error
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN messages

# Suppress Python warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# Suppress MLflow warnings
logging.getLogger('mlflow').setLevel(logging.ERROR)
logging.getLogger('mlflow.utils.environment').setLevel(logging.ERROR)
logging.getLogger('mlflow.utils.uv_utils').setLevel(logging.ERROR)
logging.getLogger('mlflow.models.model').setLevel(logging.ERROR)
logging.getLogger('mlflow.store.model_registry').setLevel(logging.ERROR)

# Suppress TensorFlow logging
logging.getLogger('tensorflow').setLevel(logging.ERROR)
