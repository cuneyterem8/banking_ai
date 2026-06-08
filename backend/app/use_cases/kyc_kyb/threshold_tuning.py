from sklearn.metrics import f1_score, precision_recall_curve

from app.use_cases.kyc_kyb.metrics import MINIMUM_RECALL_TARGET, OPERATIONAL_THRESHOLD


def find_operational_threshold(y_true: list[int], scores: list[float]) -> float:
    if len(set(y_true)) < 2:
        return OPERATIONAL_THRESHOLD
    precisions, recalls, thresholds = precision_recall_curve(y_true, scores)
    best_score = -1.0
    best_threshold = OPERATIONAL_THRESHOLD
    fallback_score = -1.0
    fallback_threshold = OPERATIONAL_THRESHOLD
    for index, threshold in enumerate(thresholds):
        precision = float(precisions[index + 1])
        recall = float(recalls[index + 1])
        if precision + recall == 0:
            continue
        f1 = 2 * precision * recall / (precision + recall)
        if f1 > fallback_score:
            fallback_score = f1
            fallback_threshold = float(threshold)
        if recall >= MINIMUM_RECALL_TARGET and f1 > best_score:
            best_score = f1
            best_threshold = float(threshold)
    selected = best_threshold if best_score >= 0 else fallback_threshold
    return max(0.05, min(0.9, selected))


def f1_at_threshold(y_true: list[int], scores: list[float], threshold: float) -> float:
    predictions = [1 if score >= threshold else 0 for score in scores]
    return float(f1_score(y_true, predictions, zero_division=0))
