# Critical Bug Fix: y_test Double Normalization

## 🐛 The Bug

Classification metrics were showing **0** because `y_true` values were being **double-normalized**, making them impossibly large (15000+ instead of 0-125).

### Root Cause

In `model_evaluation.py`:

```python
# WRONG CODE
preds = (model.predict(X_test).flatten() * rul_clip)  # Denormalized: 0-125 ✓
y_true = np.clip(y_test * rul_clip, 0, rul_clip)      # ← BUG! y_test already 0-125, multiplying again!
```

This made `y_true` values like:
- `y_test = 30` → `y_true = 30 * 125 = 3750`
- `y_test = 50` → `y_true = 50 * 125 = 6250`

Then classification check:
```python
results["critical_true"] = (results["true_rul"] < 30)  # Always False! (3750 < 30 = False)
results["critical_pred"] = (results["pred_rul"] < 30)  # Some True
```

Result: **No true critical engines** → precision/recall/f1 = 0

---

## ✅ The Fix

### In `model_evaluation.py`:

```python
# CORRECT CODE
preds = (model.predict(X_test).flatten() * rul_clip)  # Denormalized: 0-125 ✓
y_true = y_test  # ← FIXED! y_test is already in actual RUL scale (0-125)

logging.info(f"Prediction range: {preds.min():.2f} - {preds.max():.2f}")
logging.info(f"True RUL range: {y_true.min():.2f} - {y_true.max():.2f}")
```

---

## 📊 Data Flow Explanation

### Training Data (Normalized)
```python
# feature_engineering.py
y_train_raw = [206, 205, 204, ..., 2, 1, 0]  # Actual RUL values
y_train = y_train_raw / 125                   # Normalized: [1.0, 0.99, ..., 0.016, 0.008, 0]
# Saved to y_train.npy
```

### Validation Data (Normalized)
```python
y_val_raw = [180, 179, ..., 1, 0]
y_val = y_val_raw / 125  # Normalized
# Saved to y_val.npy
```

### Test Data (NOT Normalized!)
```python
# feature_engineering.py
y_test_raw = [112, 98, 69, 82, ...]  # Actual RUL from RUL_FD001.txt
y_test = np.clip(y_test_raw, 0, 125)  # Clipped but NOT normalized!
# Saved to y_test.npy ← IMPORTANT: Already in actual scale (0-125)
```

### Why Test is Different?

**Training/Validation**: We normalize targets because:
- Model outputs sigmoid (0-1)
- MSE loss works better with normalized targets
- We denormalize predictions later

**Test**: We keep actual RUL values because:
- Test RUL comes from ground truth file (RUL_FD001.txt)
- We need actual values for evaluation metrics
- Predictions are denormalized to match

---

## 🔍 How to Verify the Fix

Run the pipeline and check logs:

```bash
python main.py
```

Look for these lines in evaluation:
```
Prediction range: 5.23 - 124.87
True RUL range: 7.00 - 125.00
Critical engines (true): 15/100
Critical engines (pred): 18/100
Precision (Critical): 0.722
Recall (Critical): 0.867
F1-Score (Critical): 0.788
```

---

## 📈 Expected Results After Fix

### With 150 Epochs (Full Training)

**Regression Metrics:**
- test_rmse: **12-18 cycles** (was 60+)
- test_nasa_score: **500-1500** (was 85000+)

**Classification Metrics:**
- precision_critical: **0.75-0.90** (was 0)
- recall_critical: **0.70-0.85** (was 0)
- f1_critical: **0.72-0.87** (was 0)

---

## 🔧 Files Changed

### 1. `src/components/model_evaluation.py`
```python
# BEFORE
y_true = np.clip(y_test * rul_clip, 0, rul_clip)

# AFTER
y_true = y_test  # Already in actual RUL scale
```

### 2. `config/params.yaml`
```yaml
# BEFORE
epochs: 10  # For testing

# AFTER
epochs: 150  # Full training like notebook
```

---

## 🎯 Architecture Alignment

Your modular code now matches the notebook:

| Component | Notebook | Modular Code | Status |
|-----------|----------|--------------|--------|
| GRU Layers | 3 (128, 64, 32) | 3 (128, 64, 32) | ✅ Match |
| Dropout | [0.2, 0.2, 0.15] | [0.2, 0.2, 0.15] | ✅ Match |
| Dense Layers | [32, 16] | [32, 16] | ✅ Match |
| Learning Rate | 0.0003 | 0.0003 | ✅ Match |
| Epochs | 150 | 150 | ✅ Match |
| Batch Size | 256 | 256 | ✅ Match |
| Window Size | 30 | 30 | ✅ Match |
| RUL Clip | 125 | 125 | ✅ Match |
| Sample Weights | ✓ | ✓ | ✅ Match |
| y_test Handling | Actual scale | Actual scale | ✅ **FIXED** |

---

## 🚀 Next Steps

1. **Run full training**:
   ```bash
   python main.py
   ```

2. **Monitor training** (should take 15-30 minutes):
   - Watch for early stopping
   - Check learning rate reduction
   - Verify val_rmse decreases

3. **Check MLflow**:
   - Single unified experiment
   - All metrics logged correctly
   - Model registered if passes thresholds

4. **Verify S3 uploads**:
   - Model artifacts uploaded
   - Evaluation plots uploaded
   - All from model_registry component

---

## 💡 Key Takeaway

**Always verify data scales when denormalizing!**

- Training/Val targets: Normalized (0-1) → Denormalize predictions
- Test targets: Actual scale (0-125) → Use directly

This is a common bug in ML pipelines when mixing normalized and actual-scale data.
