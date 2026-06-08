from sklearn.metrics import f1_score, precision_recall_curve


def find_best_f1_threshold(y_true: list[int], scores: list[float]) -> float:
    if len(set(y_true)) < 2:
        return 0.28
    precisions, recalls, thresholds = precision_recall_curve(y_true, scores)
    best_f1 = -1.0
    best_threshold = 0.28
    for index, threshold in enumerate(thresholds):
        precision = float(precisions[index + 1])
        recall = float(recalls[index + 1])
        if precision + recall == 0:
            continue
        f1 = 2 * precision * recall / (precision + recall)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = float(threshold)
    return max(0.05, min(0.85, best_threshold))


def f1_at_threshold(y_true: list[int], scores: list[float], threshold: float) -> float:
    predictions = [1 if score >= threshold else 0 for score in scores]
    return float(f1_score(y_true, predictions, zero_division=0))
