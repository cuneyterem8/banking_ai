"""
Metric selection for Fraud Detection (imbalanced binary classification).

Primary: PR-AUC (sklearn ``average_precision_score``)
-------------------------------------------------------
* Summarizes the precision–recall trade-off for the fraud (positive) class.
* Preferred over ROC-AUC when positives are rare or costly to miss, because ROC
  can stay high when the model ranks negatives well while fraud precision is weak.
* Used for model selection, leaderboard comparison, and the headline ``primary_score``.

Why not accuracy?
* Dominated by the majority (legitimate) class; a model can score high accuracy
  while missing most fraud.

Why not ROC-AUC alone?
* Still reported as a secondary ranking metric, but not used to pick the best model.

Operational metrics at the validation-calibrated threshold
----------------------------------------------------------
* Precision — share of flagged transactions that are truly fraud (limits false blocks).
* Recall — share of fraud caught (limits financial loss).
* F1 — harmonic balance; shown for context at the fixed threshold, not for model selection.
"""

PRIMARY_METRIC = "average_precision"
PRIMARY_METRIC_LABEL = "PR-AUC"
AUTOGLUON_EVAL_METRIC = "average_precision"

# Per-transaction prediction quality tiers (UI / explainability at operational threshold).
PREDICTION_GOOD_MIN_CONFIDENCE = 0.55
PREDICTION_AVERAGE_MIN_CONFIDENCE = 0.35
OPERATIONAL_THRESHOLD = 0.5
