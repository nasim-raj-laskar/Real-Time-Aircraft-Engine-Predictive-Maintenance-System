# Classification Metrics Fix

## Issue

The classification metrics (precision_critical, recall_critical, f1_critical) were showing **0** in MLflow, even though the model was making predictions.

## Root Cause

The issue was in how the classification report dictionary keys were being accessed:

```python
# WRONG - Looking for string key "True"
cls_report.get("True", {}).get("precision", 0)
```

The sklearn `classification_report` with `output_dict=True` returns different key formats depending on how it's called:
- Without `target_names`: Returns boolean keys `True`/`False` 
- With `target_names`: Returns string keys like `"Critical"`/`"Non-Critical"`

## Solution

### 1. Updated `scores.py`

Added explicit `target_names` to make the keys predictable:

```python
def compute_classification_report(y_true, y_pred):
    """Compute classification report with proper handling of boolean labels."""
    # Convert to numpy arrays and ensure boolean type
    y_true = np.array(y_true, dtype=bool)
    y_pred = np.array(y_pred, dtype=bool)
    
    # Get classification report with named classes
    report = classification_report(
        y_true, 
        y_pred, 
        output_dict=True, 
        zero_division=0,
        target_names=['Non-Critical', 'Critical']  # ← KEY FIX
    )
    
    return report
```

### 2. Updated `model_evaluation.py`

Extract metrics using the correct key name:

```python
# CORRECT - Using target_name "Critical"
critical_metrics = cls_report.get("Critical", {})

precision_critical = critical_metrics.get("precision", 0)
recall_critical = critical_metrics.get("recall", 0)
f1_critical = critical_metrics.get("f1-score", 0)
```

### 3. Added Debugging Logs

To help diagnose issues in the future:

```python
# Log distribution
n_critical_true = results["critical_true"].sum()
n_critical_pred = results["critical_pred"].sum()
logging.info(f"Critical engines (true): {n_critical_true}/{len(results)}")
logging.info(f"Critical engines (pred): {n_critical_pred}/{len(results)}")

# Log report structure
logging.info(f"Classification report keys: {cls_report.keys()}")
```

## Classification Report Structure

After the fix, the report looks like:

```python
{
    'Non-Critical': {
        'precision': 0.95,
        'recall': 0.98,
        'f1-score': 0.96,
        'support': 85
    },
    'Critical': {
        'precision': 0.82,  # ← We extract this
        'recall': 0.67,     # ← We extract this
        'f1-score': 0.74,   # ← We extract this
        'support': 15
    },
    'accuracy': 0.93,
    'macro avg': {...},
    'weighted avg': {...}
}
```

## What the Metrics Mean

### Critical Engine Classification

An engine is classified as **Critical** if:
```python
predicted_RUL < 30 cycles
```

### Metrics Interpretation

- **Precision (Critical)**: Of all engines predicted as critical, what % are actually critical?
  - High precision = Few false alarms
  
- **Recall (Critical)**: Of all actually critical engines, what % did we detect?
  - High recall = Few missed critical engines
  
- **F1-Score (Critical)**: Harmonic mean of precision and recall
  - Balanced metric

### Example Scenario

```
Total test engines: 100
Actually critical (RUL < 30): 15 engines
Predicted critical: 20 engines
Correctly predicted critical: 12 engines

Precision = 12/20 = 0.60  (60% of predictions were correct)
Recall = 12/15 = 0.80     (80% of critical engines detected)
F1-Score = 2 * (0.60 * 0.80) / (0.60 + 0.80) = 0.69
```

## Expected Values

### With Few Training Epochs (Testing)

Your current results show the model is undertrained:
- **test_rmse: 59.97** (very high - should be < 20)
- **test_nasa_score: 85108** (very high - should be < 2000)

This means predictions are very inaccurate, so classification metrics will also be poor.

### With Proper Training (100 epochs)

Expected metrics:
- **test_rmse**: 12-18 cycles
- **test_nasa_score**: 500-1500
- **precision_critical**: 0.75-0.90
- **recall_critical**: 0.70-0.85
- **f1_critical**: 0.72-0.87

## Why Metrics Were 0 Before

The code was looking for key `"True"` but sklearn was returning:
- Either boolean key `True` (not string)
- Or with our fix, string key `"Critical"`

So `cls_report.get("True", {})` returned empty dict `{}`, and then `.get("precision", 0)` returned the default `0`.

## Testing the Fix

Run the pipeline and check logs:

```bash
python main.py
```

Look for these log lines:
```
Critical engines (true): 15/100
Critical engines (pred): 20/100
Classification report keys: dict_keys(['Non-Critical', 'Critical', 'accuracy', 'macro avg', 'weighted avg'])
Precision (Critical): 0.600
Recall (Critical): 0.800
F1-Score (Critical): 0.686
```

## Files Changed

1. ✅ `src/metrics/scores.py` - Added `target_names` parameter
2. ✅ `src/components/model_evaluation.py` - Fixed key access and added logging

## Next Steps

1. Train with full epochs (100) to get meaningful metrics
2. Check if classification threshold of 30 cycles is appropriate for your use case
3. Consider adjusting threshold based on maintenance lead time requirements
