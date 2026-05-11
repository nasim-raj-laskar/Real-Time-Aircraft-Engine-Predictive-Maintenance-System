import numpy as np
from sklearn.metrics import mean_squared_error, classification_report


def compute_rmse(y_true, y_pred):
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def compute_nasa_score(y_true, y_pred):
    d = y_pred.flatten() - y_true.flatten()
    return float(np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1)))


def compute_classification_report(y_true, y_pred):
    return classification_report(y_true, y_pred, output_dict=True, zero_division=0)
