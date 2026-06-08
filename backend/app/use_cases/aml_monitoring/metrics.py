"""Metric selection for AML alert prioritization."""

PRIMARY_METRIC = "average_precision"
PRIMARY_METRIC_LABEL = "PR-AUC"
AUTOGLUON_EVAL_METRIC = "average_precision"

OPERATIONAL_THRESHOLD = 0.34
MINIMUM_RECALL_TARGET = 0.55
