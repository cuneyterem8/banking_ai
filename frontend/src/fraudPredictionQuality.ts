import type { FraudDecision } from "./api";

/** Matches backend ``metrics.py`` — used for row-level prediction colouring. */
export const PREDICTION_GOOD_MIN_CONFIDENCE = 0.55;
export const PREDICTION_AVERAGE_MIN_CONFIDENCE = 0.35;
/** Fallback only; live threshold comes from evaluation.threshold after val calibration. */
export const OPERATIONAL_THRESHOLD = 0.5;

export type PredictionQuality = "good" | "average" | "bad";

export function predictionConfidence(actualIsFraud: number, fraudProbability: number): number {
  return actualIsFraud === 1 ? fraudProbability : 1 - fraudProbability;
}

export function classifyPredictionQuality(
  actualIsFraud: number,
  predictedIsFraud: number,
  fraudProbability: number
): PredictionQuality {
  if (actualIsFraud !== predictedIsFraud) {
    return "bad";
  }
  const confidence = predictionConfidence(actualIsFraud, fraudProbability);
  if (confidence >= PREDICTION_GOOD_MIN_CONFIDENCE) {
    return "good";
  }
  if (confidence >= PREDICTION_AVERAGE_MIN_CONFIDENCE) {
    return "average";
  }
  return "average";
}

export function qualityFromDecision(decision: FraudDecision): PredictionQuality {
  return classifyPredictionQuality(
    decision.actual_is_fraud,
    decision.predicted_is_fraud,
    decision.fraud_probability
  );
}

export function qualityLabel(quality: PredictionQuality): string {
  if (quality === "good") return "Good";
  if (quality === "average") return "Average";
  return "Bad";
}

export function qualityTextClass(quality: PredictionQuality): string {
  if (quality === "good") return "font-medium text-emerald-400";
  if (quality === "average") return "font-medium text-yellow-400";
  return "font-medium text-red-400";
}

/** Model-level score tiers (PR-AUC ~0.23 → bad; ~0.35 → average; ≥0.5 → good). */
export const METRIC_GOOD_MIN = 0.5;
export const METRIC_AVERAGE_MIN = 0.3;

export type MetricKind = "pr_auc" | "roc_auc" | "f1" | "precision" | "recall" | "accuracy";

export function classifyMetricScore(
  kind: MetricKind,
  value: number | null | undefined,
  context?: { precision?: number | null; recall?: number | null }
): PredictionQuality | null {
  if (value == null || Number.isNaN(value)) {
    return null;
  }
  if (kind === "accuracy" && context) {
    const precision = context.precision ?? 0;
    const recall = context.recall ?? 0;
    if (precision < 0.15 && recall < 0.15) {
      return "bad";
    }
  }
  if (value >= METRIC_GOOD_MIN) {
    return "good";
  }
  if (value >= METRIC_AVERAGE_MIN) {
    return "average";
  }
  return "bad";
}

export function qualityPanelClass(quality: PredictionQuality): string {
  if (quality === "good") {
    return "border-emerald-700/60 bg-emerald-950/40";
  }
  if (quality === "average") {
    return "border-yellow-700/50 bg-yellow-950/25";
  }
  return "border-red-800/50 bg-red-950/25";
}

export function metricQualityLabel(quality: PredictionQuality | null): string {
  if (quality == null) return "";
  return ` (${qualityLabel(quality)})`;
}
