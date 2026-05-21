import time
import random
import requests

ENGINE_ID = "STREAM-TEST-1"
BASE = "http://localhost:8000"

# required sensor keys (order not important for push)
FEATURES = [
    "s2","s3","s4","s7","s9","s11","s12","s14","s17","s20","s21"
]

# push 30 synthetic readings
for i in range(30):
    reading = {k: random.uniform(0.0, 1.0) for k in FEATURES}
    resp = requests.post(f"{BASE}/push", json={"engine_id": ENGINE_ID, "reading": reading})
    if resp.status_code != 200:
        print("Push failed:", resp.status_code, resp.text)
        break
    if (i + 1) % 10 == 0:
        print(f"Pushed {i+1} readings")
    time.sleep(0.05)

# request stream prediction
resp = requests.get(f"{BASE}/predict/stream/{ENGINE_ID}")
if resp.status_code == 200:
    print("Prediction:", resp.json())
else:
    print("Prediction failed:", resp.status_code, resp.text)
