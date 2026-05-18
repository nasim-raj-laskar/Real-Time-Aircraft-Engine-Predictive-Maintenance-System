import numpy as np
import requests

X_test = np.load("artifacts/data_feature_engineering/X_test.npy")
y_test = np.load("artifacts/data_feature_engineering/y_test.npy")

for i in [0, 10, 50, 99]:
    resp = requests.post("http://localhost:8000/predict", json={
        "engine_id": f"ENG-{i}",
        "sensor_data": X_test[i].tolist()
    }).json()
    print(f"ENG-{i:>2} | Predicted: {resp['remaining_cycles']:>4} | True: {y_test[i]:>6.1f} | Risk: {resp['risk_level']}")
