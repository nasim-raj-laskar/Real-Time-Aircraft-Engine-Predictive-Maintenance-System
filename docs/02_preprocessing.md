# Preprocessing Pipeline

## Overview

Raw C-MAPSS data cannot be fed directly into a model. This document covers every preprocessing step in order, with the reasoning behind each decision.

---

## Step 1 — Load Raw Data

```python
import pandas as pd

COLS = ['unit', 'cycle', 'os1', 'os2', 'os3'] + [f's{i}' for i in range(1, 22)]

def load_data(path: str) -> pd.DataFrame:
    return pd.read_csv(
        path, sep=' +', header=None,
        usecols=range(26), names=COLS, engine='python'
    )

train = load_data('Dataset/train_FD001.txt')
test  = load_data('Dataset/test_FD001.txt')
rul   = pd.read_csv('Dataset/RUL_FD001.txt', header=None, names=['rul'])
```

---

## Step 2 — Drop Useless Sensors and Settings

10 sensors have near-zero variance across all cycles — they carry no degradation signal.

```python
DROP_SENSORS = ['s1', 's5', 's6', 's8', 's10', 's13', 's15', 's16', 's18', 's19']
DROP_SETTINGS = ['os3']  # single value in FD001/FD003; keep for FD002/FD004

KEEP_SENSORS = ['s2', 's3', 's4', 's7', 's9', 's11', 's12', 's14', 's17', 's20', 's21']

train.drop(columns=DROP_SENSORS + DROP_SETTINGS, inplace=True)
test.drop(columns=DROP_SENSORS + DROP_SETTINGS, inplace=True)
```

Why: Including constant features adds noise to tree-based models and wastes LSTM capacity.

---

## Step 3 — Compute RUL Labels (Training Data Only)

The training files run each engine to failure, so RUL is derived from the max cycle:

```python
def add_rul(df: pd.DataFrame) -> pd.DataFrame:
    max_cycle = df.groupby('unit')['cycle'].transform('max')
    df['RUL'] = max_cycle - df['cycle']
    return df

train = add_rul(train)
```

For the test set, RUL at the last cycle is provided in `RUL_FD00X.txt`. Attach it:

```python
last_cycles = test.groupby('unit')['cycle'].max().reset_index()
last_cycles['RUL'] = rul['rul'].values
test = test.merge(last_cycles[['unit', 'RUL']], on='unit', how='left')
# Keep only the last cycle row per engine for evaluation
test_last = test.groupby('unit').last().reset_index()
```

---

## Step 4 — Clip RUL (Piecewise Linear Target)

Early in engine life, RUL can be 300+ cycles. The engine shows no degradation signal that far out — predicting it accurately is impossible and irrelevant.

Clip RUL to a maximum value so the model focuses on the degradation window:

```python
RUL_CLIP = 125  # standard choice for C-MAPSS; tune per dataset

train['RUL'] = train['RUL'].clip(upper=RUL_CLIP)
```

Effect: RUL stays flat at 125 during healthy operation, then decreases linearly as the engine degrades. This is the piecewise linear RUL formulation used in most literature.

Tuning guidance:
- FD001/FD002: 125 works well
- FD003/FD004: try 130–150 (longer engine lives)

---

## Step 5 — Operating Condition Normalization

### FD001 / FD003 (single condition)

Simple global MinMax normalization:

```python
from sklearn.preprocessing import MinMaxScaler

scaler = MinMaxScaler()
train[KEEP_SENSORS] = scaler.fit_transform(train[KEEP_SENSORS])
test[KEEP_SENSORS]  = scaler.transform(test[KEEP_SENSORS])  # never refit on test
```

### FD002 / FD004 (6 operating conditions)

Raw sensor values shift dramatically between conditions. Global normalization will not work — the model will learn condition identity instead of degradation.

Cluster operating conditions first, then normalize within each cluster:

```python
from sklearn.cluster import KMeans

SETTING_COLS = ['os1', 'os2', 'os3']

kmeans = KMeans(n_clusters=6, random_state=42, n_init=10)
train['condition'] = kmeans.fit_predict(train[SETTING_COLS])
test['condition']  = kmeans.predict(test[SETTING_COLS])

# Normalize per condition
for cond in range(6):
    mask_tr = train['condition'] == cond
    mask_te = test['condition'] == cond
    sc = MinMaxScaler()
    train.loc[mask_tr, KEEP_SENSORS] = sc.fit_transform(train.loc[mask_tr, KEEP_SENSORS])
    test.loc[mask_te, KEEP_SENSORS]  = sc.transform(test.loc[mask_te, KEEP_SENSORS])
```

Save the KMeans model and per-condition scalers — they are required at inference time.

---

## Step 6 — Rolling Window Features

A single cycle row has no temporal context. The model needs to see the trend.

### Option A — Engineered Rolling Statistics (for tree models)

```python
def add_rolling_features(df: pd.DataFrame, windows: list[int] = [10, 20, 30]) -> pd.DataFrame:
    df = df.sort_values(['unit', 'cycle'])
    for w in windows:
        for s in KEEP_SENSORS:
            grp = df.groupby('unit')[s]
            df[f'{s}_mean_{w}'] = grp.transform(lambda x: x.rolling(w, min_periods=1).mean())
            df[f'{s}_std_{w}']  = grp.transform(lambda x: x.rolling(w, min_periods=1).std().fillna(0))
    return df

train = add_rolling_features(train)
test  = add_rolling_features(test)
```

### Option B — Sliding Window Sequences (for LSTM)

```python
import numpy as np

WINDOW = 30

def build_sequences(df: pd.DataFrame, feature_cols: list[str], window: int = WINDOW):
    X, y = [], []
    for _, engine_df in df.groupby('unit'):
        engine_df = engine_df.sort_values('cycle')
        data = engine_df[feature_cols].values
        labels = engine_df['RUL'].values
        for i in range(len(data) - window + 1):
            X.append(data[i:i+window])
            y.append(labels[i+window-1])
    return np.array(X), np.array(y)

X_train, y_train = build_sequences(train, KEEP_SENSORS)
# X_train shape: (n_samples, 30, 11)
```

For engines with fewer than `window` cycles, pad with the first row repeated:

```python
def pad_engine(engine_df: pd.DataFrame, window: int, feature_cols: list[str]) -> np.ndarray:
    data = engine_df[feature_cols].values
    if len(data) < window:
        pad = np.repeat(data[:1], window - len(data), axis=0)
        data = np.vstack([pad, data])
    return data[-window:]  # last window for inference
```

---

## Step 7 — Train/Validation Split

Do NOT split randomly — engines must stay intact. Split by engine ID:

```python
from sklearn.model_selection import GroupShuffleSplit

gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, val_idx = next(gss.split(train, groups=train['unit']))

df_train = train.iloc[train_idx]
df_val   = train.iloc[val_idx]
```

Random row splits would leak future cycles of an engine into the validation set.

---

## Preprocessing Checklist

| Step | FD001 | FD002 | FD003 | FD004 |
|------|-------|-------|-------|-------|
| Drop constant sensors | ✓ | ✓ | ✓ | ✓ |
| Drop os3 | ✓ | — | ✓ | — |
| Compute RUL | ✓ | ✓ | ✓ | ✓ |
| Clip RUL at 125 | ✓ | ✓ | ✓ | ✓ |
| Global normalization | ✓ | — | ✓ | — |
| Condition clustering + per-condition norm | — | ✓ | — | ✓ |
| Rolling features / sequences | ✓ | ✓ | ✓ | ✓ |
| Group-based train/val split | ✓ | ✓ | ✓ | ✓ |

---

## Artifacts to Save

Every artifact fitted on training data must be saved and reused at inference time:

```
artifacts/
├── scaler_FD001.pkl          # MinMaxScaler (or per-condition scalers)
├── kmeans_FD002.pkl          # KMeans condition clusterer (FD002/FD004 only)
├── scalers_FD002/            # Per-condition scalers (FD002/FD004 only)
│   ├── scaler_cond_0.pkl
│   └── ...
└── feature_cols.json         # List of feature columns used
```
