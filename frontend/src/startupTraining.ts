import { useQuery } from "@tanstack/react-query";

import { fetchStartupStatus, fetchTrainingStatus, type StartupStatus, type TrainingStatus } from "./api";

export const STARTUP_USE_CASE_SLUGS = [
  "fraud-detection",
  "credit-risk",
  "document-ocr",
  "support-chatbot",
  "liquidity-forecast",
  "aml-monitoring",
  "kyc-kyb",
  "email-automation",
  "market-intelligence"
] as const;

export type StartupUseCaseSlug = (typeof STARTUP_USE_CASE_SLUGS)[number];

export const TERMINAL_TRAINING_STATUSES = new Set<TrainingStatus["status"]>([
  "completed",
  "failed",
  "skipped"
]);

export function isStartupTrainingActive(status: TrainingStatus["status"] | undefined): boolean {
  return Boolean(status && !TERMINAL_TRAINING_STATUSES.has(status));
}

export function useStartupTraining(
  slug: StartupUseCaseSlug,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ["training-status", slug],
    queryFn: () => fetchTrainingStatus(slug),
    enabled: options?.enabled ?? true,
    refetchInterval: (query) => (isStartupTrainingActive(query.state.data?.status) ? 800 : false)
  });
}

export function isStartupTrainingTerminal(status: TrainingStatus["status"] | undefined): boolean {
  return Boolean(status && TERMINAL_TRAINING_STATUSES.has(status));
}

export function useStartupStatus() {
  return useQuery<StartupStatus>({
    queryKey: ["startup-status"],
    queryFn: fetchStartupStatus,
    refetchInterval: (query) => (query.state.data?.ml_training_ready ? false : 800)
  });
}

export function isStartupStageReady(status: TrainingStatus["status"] | undefined): boolean {
  return status === "completed" || status === "skipped";
}
