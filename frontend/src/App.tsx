import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, BrainCircuit, CheckCircle2, FileStack, FileText, Landmark, Mail, Menu, MessageSquare, Play, Send, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, Navigate, Route, Routes, useParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import {
  METRIC_AVERAGE_MIN,
  METRIC_GOOD_MIN,
  OPERATIONAL_THRESHOLD,
  classifyMetricScore,
  metricQualityLabel,
  qualityFromDecision,
  qualityLabel,
  qualityPanelClass,
  qualityTextClass
} from "./fraudPredictionQuality";
import {
  fetchAiHealth,
  fetchAmlMonitoringLatest,
  fetchDocumentOcrLatest,
  fetchEmailAutomationLatest,
  fetchKycKybLatest,
  fetchLiquidityForecastLatest,
  fetchRawData,
  fetchRuns,
  fetchSupportChatbotLatest,
  fetchUseCaseEvaluations,
  fetchUseCases,
  runUseCaseWithProgress,
  submitEmailDraft,
  submitSupportChatbotQuestion,
  type AmlAlertDecision,
  type AmlMonitoringPayload,
  type AmlNarrativeDraft,
  type CreditDecision,
  type DocumentExtraction,
  type DocumentOcrPayload,
  type EmailAutomationDraft,
  type EmailAutomationPayload,
  type EmailAutomationScore,
  type EmailComplianceFinding,
  type EmailDraftRequest,
  type FraudDecision,
  type KycKybExtractedDocument,
  type KycKybPackageDecision,
  type KycKybPayload,
  type KycKybRuleFinding,
  type LiquidityForecastPayload,
  type LiquidityForecastRecord,
  type LiquidityLocationProfile,
  type ModelRun,
  type RawArtifact,
  type RunProgress,
  type SplitEvaluation,
  type SupportChatbotAnswer,
  type SupportChatbotPayload,
  type SupportKnowledgeChunk
} from "./api";
import { getUseCase, USE_CASES } from "./useCases";
import {
  isStartupTrainingActive,
  STARTUP_USE_CASE_SLUGS,
  useStartupStatus,
  useStartupTraining
} from "./startupTraining";

export function App() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-72 flex-col border-r border-zinc-800 bg-zinc-950">
        <NavLink
          to="/"
          aria-label="Back to dashboard"
          className="flex h-16 items-center gap-3 border-b border-zinc-800 px-5 transition hover:bg-zinc-900"
        >
          <div className="grid h-9 w-9 place-items-center rounded-md bg-emerald-600 text-white">
            <BrainCircuit size={20} />
          </div>
          <div>
            <p className="text-sm font-semibold">Banking AI Portal</p>
            <p className="text-xs text-zinc-400">Staged real-AI MVP</p>
          </div>
        </NavLink>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {USE_CASES.map((item) => (
            <NavLink
              key={item.slug}
              to={`/use-cases/${item.slug}`}
              className={({ isActive }) =>
                [
                  "flex items-center justify-between rounded-md px-3 py-2 text-sm transition",
                  isActive ? "bg-emerald-500/15 text-emerald-200" : "text-zinc-300 hover:bg-zinc-900"
                ].join(" ")
              }
            >
              <span className="truncate">{item.title}</span>
              <span
                className={[
                  "rounded-full px-2 py-0.5 text-[11px]",
                  item.status === "implemented" ? "bg-emerald-500/20 text-emerald-200" : "bg-zinc-800 text-zinc-400"
                ].join(" ")}
              >
                {item.status === "implemented" ? "Live" : `Stage ${item.order}`}
              </span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="ml-72 min-h-screen">
        <StartupTrainingStrip />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/use-cases/:slug" element={<UseCasePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function StartupTrainingStrip() {
  const startup = useStartupStatus();
  const data = startup.data;
  const active = data?.active_stage ?? null;

  if (!active || data?.ml_training_ready) {
    return null;
  }

  /*
  const legacyActive = showFraud
    ? {
        title: "Fraud Detection",
        percent: fraud.data?.progress_percent ?? 0,
        stage: fraud.data?.stage ?? "…"
      }
    : {
        title: "Credit Risk",
        percent: credit.data?.progress_percent ?? 0,
        stage: credit.data?.stage ?? "…"
      };

  return (
    <div className="border-b border-zinc-800 bg-zinc-900/95 px-8 py-4">
      <p className="mb-2 text-sm font-medium text-zinc-200">
        Startup training — {active.title} ({showFraud ? "1/2" : "2/2"})
      </p>
      <ProgressBar percent={active.percent} stage={`${active.stage}`} />
    </div>
  );
}

  */

  return (
    <div className="border-b border-zinc-800 bg-zinc-900/95 px-8 py-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium text-zinc-200">
          Startup training - {active.title ?? active.use_case_slug} ({active.order ?? 1}/{data?.total_stage_count ?? STARTUP_USE_CASE_SLUGS.length})
        </p>
        <p className="text-xs text-zinc-500">
          {data?.completed_stage_count ?? 0} of {data?.total_stage_count ?? STARTUP_USE_CASE_SLUGS.length} stages complete
        </p>
      </div>
      <ProgressBar percent={active.progress_percent ?? 0} stage={`${active.stage ?? "queued"}`} />
      <div className="mt-3 grid gap-2 md:grid-cols-4 xl:grid-cols-8">
        {(data?.stages ?? []).map((stage) => (
          <div
            key={stage.use_case_slug}
            className={`flex items-center gap-2 rounded-md border px-2 py-1 text-xs ${
              stage.status === "completed"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
                : stage.status === "running" || stage.status === "queued"
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-100"
                  : stage.status === "failed"
                    ? "border-red-500/30 bg-red-500/10 text-red-200"
                    : "border-zinc-800 bg-zinc-950 text-zinc-500"
            }`}
          >
            {stage.status === "completed" ? <CheckCircle2 size={13} /> : <Activity size={13} />}
            <span className="truncate">{stage.order}. {stage.title}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Dashboard() {
  const useCases = useQuery({ queryKey: ["use-cases"], queryFn: fetchUseCases });
  const aiHealth = useQuery({ queryKey: ["ai-health"], queryFn: fetchAiHealth });
  const startup = useStartupStatus();
  const items = useCases.data?.items ?? [];
  const startupReadySlugs = new Set(
    (startup.data?.stages ?? []).filter((stage) => stage.status === "completed").map((stage) => stage.use_case_slug)
  );
  const fallbackCount = items.filter((item) => {
    if ((STARTUP_USE_CASE_SLUGS as readonly string[]).includes(item.slug) && !startupReadySlugs.has(item.slug)) {
      return false;
    }
    const provider = item.latest_run?.provider_used ?? "";
    return provider === "openai" || provider.includes("gpt-4o");
  }).length;

  return (
    <section className="space-y-6 p-8">
      <PageTitle
        icon={<Activity size={22} />}
        title="Banking AI Operations"
        subtitle="Local-first staged MVP with synthetic banking data and PostgreSQL persistence."
      />
      <div className="grid grid-cols-5 gap-4">
        <MetricCard label="Use Cases" value={items.length || 10} />
        <MetricCard label="Implemented" value={items.filter((item) => item.status === "implemented").length || 1} />
        <MetricCard label="Raw Artifacts" value={items.reduce((sum, item) => sum + (item.artifact_count ?? 0), 0)} />
        <MetricCard label="Startup Stage" value={`${startup.data?.completed_stage_count ?? 0}/${startup.data?.total_stage_count ?? STARTUP_USE_CASE_SLUGS.length}`} />
        <MetricCard label="GPT-4o Fallbacks" value={fallbackCount} />
      </div>
      <div className="grid grid-cols-[1.3fr_0.7fr] gap-5">
        <Panel title="Use Case Roadmap">
          <div className="grid gap-3">
            {(items.length ? items : USE_CASES).map((item) => {
              const stage = startup.data?.stages.find((entry) => entry.use_case_slug === item.slug);
              return (
                <div key={item.slug} className="flex items-center justify-between rounded-md border border-zinc-800 bg-zinc-900 p-3">
                <div>
                  <p className="font-medium">{item.title}</p>
                  <p className="text-sm text-zinc-400">{stage ? `${item.category} - ${stage.status}` : item.category}</p>
                </div>
                <span className={item.status === "implemented" ? "badge-live" : "badge-planned"}>
                  {item.status === "implemented" ? "Implemented" : "Planned"}
                </span>
              </div>
              );
            })}
          </div>
        </Panel>
        <Panel title="Adapter Readiness">
          <div className="space-y-3">
            {aiHealth.data?.adapters.map((adapter) => (
              <div key={adapter.name} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                <div className="flex items-center justify-between">
                  <p className="font-medium">{adapter.name}</p>
                  {adapter.available ? <CheckCircle2 className="text-emerald-600" size={18} /> : <AlertTriangle className="text-amber-600" size={18} />}
                </div>
                <p className="mt-1 text-sm text-zinc-400">{adapter.message}</p>
              </div>
            ))}
            {aiHealth.isError ? <ErrorBox message={(aiHealth.error as Error).message} /> : null}
          </div>
        </Panel>
      </div>
    </section>
  );
}

function UseCasePage() {
  const { slug } = useParams();
  const item = getUseCase(slug);
  if (!item) {
    return <section className="p-8">Use case not found.</section>;
  }
  if (item.slug === "fraud-detection") {
    return <FraudDetectionPage />;
  }
  if (item.slug === "credit-risk") {
    return <CreditRiskPage />;
  }
  if (item.slug === "document-ocr") {
    return <DocumentOcrPage />;
  }
  if (item.slug === "support-chatbot") {
    return <SupportChatbotPage />;
  }
  if (item.slug === "liquidity-forecast") {
    return <LiquidityForecastPage />;
  }
  if (item.slug === "aml-monitoring") {
    return <AmlMonitoringPage />;
  }
  if (item.slug === "kyc-kyb") {
    return <KycKybPage />;
  }
  if (item.slug === "email-automation") {
    return <EmailAutomationPage />;
  }
  return (
    <section className="space-y-6 p-8">
      <PageTitle icon={<Menu size={22} />} title={item.title} subtitle={`${item.category} - planned for stage ${item.order}.`} />
      <Panel title="Stage Gate">
        <p className="text-zinc-300">
          This section will be designed and implemented after you test and approve the previous use case.
        </p>
      </Panel>
    </section>
  );
}

function FraudDetectionPage() {
  const queryClient = useQueryClient();
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);

  const raw = useQuery({ queryKey: ["raw", "fraud-detection"], queryFn: () => fetchRawData("fraud-detection") });
  const training = useStartupTraining("fraud-detection");
  const trainingActive = isStartupTrainingActive(training.data?.status);
  const runs = useQuery({ queryKey: ["runs", "fraud-detection"], queryFn: () => fetchRuns("fraud-detection") });
  const testRunInProgress = runs.data?.items.some((run) => run.status === "running") ?? false;
  const evaluations = useQuery({
    queryKey: ["fraud-evaluations", "fraud-detection"],
    queryFn: () => fetchUseCaseEvaluations("fraud-detection"),
    refetchInterval: () =>
      trainingActive || testRunInProgress || runProgress !== null ? 1000 : false
  });
  const trainingReady = training.data?.status === "completed";
  const valEvaluation = trainingReady ? evaluations.data?.val?.evaluation ?? null : null;
  const activeTestEvaluation = trainingReady ? evaluations.data?.test?.evaluation ?? null : null;
  const latestTestRun = trainingReady ? evaluations.data?.test?.run ?? null : null;

  const runMutation = useMutation({
    mutationFn: () =>
      runUseCaseWithProgress(
        "fraud-detection",
        (progress) => {
          setRunProgress(progress);
        },
        "Fraud model run failed."
      ),
    onSuccess: () => {
      setRunProgress(null);
      queryClient.invalidateQueries({ queryKey: ["fraud-evaluations", "fraud-detection"] });
      queryClient.invalidateQueries({ queryKey: ["runs", "fraud-detection"] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    },
    onError: () => setRunProgress(null)
  });

  useEffect(() => {
    if (trainingActive) {
      queryClient.setQueryData(["fraud-evaluations", "fraud-detection"], {
        use_case_slug: "fraud-detection",
        val: null,
        test: null
      });
    }
    if (training.data?.status === "completed") {
      queryClient.invalidateQueries({ queryKey: ["fraud-evaluations", "fraud-detection"] });
    }
  }, [trainingActive, training.data?.status, queryClient]);

  const trainDataset = raw.data?.datasets.find((d) => d.dataset_key === "train");
  const valDataset = raw.data?.datasets.find((d) => d.dataset_key === "val");
  const testDataset = raw.data?.datasets.find((d) => d.dataset_key === "test");
  const valPreview = valDataset?.payload.preview ?? valDataset?.payload.records ?? [];
  const testPreview = testDataset?.payload.preview ?? testDataset?.payload.records ?? [];

  return (
    <section className="space-y-6 p-8">
      <PageTitle
        icon={<AlertTriangle size={22} />}
        title="Fraud Detection"
        subtitle="Each startup retrains from scratch, saves validation to the database, then test predictions are saved after Run Fraud Model. Metrics and tables load from the database only."
      />
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Train Records" value={trainDataset?.payload.record_count ?? 0} />
        <MetricCard label="Val Records" value={valDataset?.payload.record_count ?? 0} />
        <MetricCard label="Test Records" value={testDataset?.payload.record_count ?? 0} />
        <MetricCard
          label="Training Status"
          value={training.data?.status ?? "loading"}
        />
      </div>
      <FraudOverviewPanel
        trainCount={trainDataset?.payload.record_count ?? 0}
        valCount={valDataset?.payload.record_count ?? 0}
        testCount={testDataset?.payload.record_count ?? 0}
      />
      <div className="grid grid-cols-[1fr_0.9fr] gap-5">
        <Panel title="Raw Artifacts">
          <div className="space-y-3">
            {raw.data?.artifacts.map((artifact) => (
              <div key={artifact.id} className="flex items-center gap-3 rounded-md border border-zinc-800 bg-zinc-950 p-3">
                <FileStack size={18} className="text-emerald-300" />
                <div>
                  <p className="font-medium">{artifact.file_name}</p>
                  <p className="text-xs text-zinc-400">
                    {artifact.dataset_key} - {artifact.artifact_type.toUpperCase()}
                  </p>
                </div>
              </div>
            ))}
            {raw.isError ? <ErrorBox message={(raw.error as Error).message} /> : null}
          </div>
        </Panel>
        <Panel title="Run Adapter">
          <div className="space-y-4">
            <p className="text-sm text-zinc-300">
              Scores the test split using the model trained at startup. Training runs automatically when the backend starts.
            </p>
            <button
              type="button"
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending || !trainingReady}
              className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
            >
              <Play size={16} />
              {runMutation.isPending ? "Running" : "Run Fraud Model"}
            </button>
            {(runMutation.isPending || runProgress) && (
              <ProgressBar
                percent={runProgress?.progress_percent ?? 0}
                stage={runProgress?.stage ?? "starting"}
              />
            )}
            {trainingActive ? (
              <ProgressBar percent={training.data?.progress_percent ?? 0} stage={`Training: ${training.data?.stage ?? "…"}`} />
            ) : null}
            {training.data?.status === "failed" ? (
              <ErrorBox message={training.data.error ?? "Startup training failed."} />
            ) : null}
            {runMutation.isError ? <ErrorBox message={(runMutation.error as Error).message} /> : null}
            {latestTestRun ? (
              <p className="text-sm text-zinc-400">Last test run: {latestTestRun.id}</p>
            ) : null}
          </div>
        </Panel>
      </div>
      <Panel title="Validation Metrics (startup training)">
        {valEvaluation ? (
          <EvaluationCharts evaluation={valEvaluation} />
        ) : trainingActive ? (
          <EmptyState text="Training in progress. Validation charts will appear when complete." />
        ) : (
          <EmptyState text="Validation metrics are not ready yet." />
        )}
      </Panel>
      <Panel title="Validation Predictions">
        {valEvaluation ? (
          <FraudPredictionTable splitLabel="validation" rows={valPreview} evaluation={valEvaluation} />
        ) : (
          <EmptyState text="Validation prediction table appears after startup training completes." />
        )}
      </Panel>
      <Panel title="Test Evaluation (Run Fraud Model)">
        {activeTestEvaluation ? (
          <EvaluationCharts evaluation={activeTestEvaluation} />
        ) : (
          <EmptyState text="Run the fraud model to see test PR-AUC, precision/recall, and confusion matrix." />
        )}
      </Panel>
      <Panel title="Test Predictions">
        {!trainingReady ? (
          <EmptyState text="Available after startup training finishes. Run Fraud Model to score the test split." />
        ) : !activeTestEvaluation ? (
          <EmptyState text="Training is complete. Click Run Fraud Model to generate test predictions in this table." />
        ) : (
          <FraudPredictionTable splitLabel="test" rows={testPreview} evaluation={activeTestEvaluation} />
        )}
      </Panel>
      <Panel title="Run History">
        <RunHistory runs={runs.data?.items ?? []} />
      </Panel>
    </section>
  );
}

function CreditRiskPage() {
  const slug = "credit-risk";
  const queryClient = useQueryClient();
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);

  const raw = useQuery({ queryKey: ["raw", slug], queryFn: () => fetchRawData(slug) });
  const training = useStartupTraining(slug);
  const trainingActive = isStartupTrainingActive(training.data?.status);
  const runs = useQuery({ queryKey: ["runs", slug], queryFn: () => fetchRuns(slug) });
  const testRunInProgress = runs.data?.items.some((run) => run.status === "running") ?? false;
  const evaluations = useQuery({
    queryKey: ["credit-evaluations", slug],
    queryFn: () => fetchUseCaseEvaluations(slug),
    refetchInterval: () =>
      trainingActive || testRunInProgress || runProgress !== null ? 1000 : false
  });

  const trainingReady = training.data?.status === "completed";
  const valEvaluation = trainingReady ? evaluations.data?.val?.evaluation ?? null : null;
  const activeTestEvaluation = trainingReady ? evaluations.data?.test?.evaluation ?? null : null;
  const latestTestRun = trainingReady ? evaluations.data?.test?.run ?? null : null;

  const runMutation = useMutation({
    mutationFn: () =>
      runUseCaseWithProgress(
        slug,
        (progress) => {
          setRunProgress(progress);
        },
        "Credit risk model run failed."
      ),
    onSuccess: () => {
      setRunProgress(null);
      queryClient.invalidateQueries({ queryKey: ["credit-evaluations", slug] });
      queryClient.invalidateQueries({ queryKey: ["runs", slug] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    },
    onError: () => setRunProgress(null)
  });

  useEffect(() => {
    if (trainingActive) {
      queryClient.setQueryData(["credit-evaluations", slug], {
        use_case_slug: slug,
        val: null,
        test: null
      });
    }
    if (training.data?.status === "completed") {
      queryClient.invalidateQueries({ queryKey: ["credit-evaluations", slug] });
    }
  }, [trainingActive, training.data?.status, queryClient, slug]);

  const trainDataset = raw.data?.datasets.find((d) => d.dataset_key === "train");
  const valDataset = raw.data?.datasets.find((d) => d.dataset_key === "val");
  const testDataset = raw.data?.datasets.find((d) => d.dataset_key === "test");
  const valPreview = valDataset?.payload.preview ?? valDataset?.payload.records ?? [];
  const testPreview = testDataset?.payload.preview ?? testDataset?.payload.records ?? [];

  return (
    <section className="space-y-6 p-8">
      <PageTitle
        icon={<Landmark size={22} />}
        title="Credit Risk"
        subtitle="Probability-of-default scoring for synthetic loan applications with train, validation, and held-out test persistence."
      />
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Train Records" value={trainDataset?.payload.record_count ?? 0} />
        <MetricCard label="Val Records" value={valDataset?.payload.record_count ?? 0} />
        <MetricCard label="Test Records" value={testDataset?.payload.record_count ?? 0} />
        <MetricCard label="Training Status" value={training.data?.status ?? "loading"} />
      </div>
      <CreditRiskOverviewPanel
        trainCount={trainDataset?.payload.record_count ?? 0}
        valCount={valDataset?.payload.record_count ?? 0}
        testCount={testDataset?.payload.record_count ?? 0}
        trainDefaults={trainDataset?.payload.label_count ?? 0}
        valDefaults={valDataset?.payload.label_count ?? 0}
        testDefaults={testDataset?.payload.label_count ?? 0}
      />
      <div className="grid grid-cols-[1fr_0.9fr] gap-5">
        <Panel title="Raw Artifacts">
          <div className="space-y-3">
            {raw.data?.artifacts.map((artifact) => (
              <div key={artifact.id} className="flex items-center gap-3 rounded-md border border-zinc-800 bg-zinc-950 p-3">
                <FileStack size={18} className="text-emerald-300" />
                <div>
                  <p className="font-medium">{artifact.file_name}</p>
                  <p className="text-xs text-zinc-400">
                    {artifact.dataset_key} - {artifact.artifact_type.toUpperCase()}
                  </p>
                </div>
              </div>
            ))}
            {raw.isError ? <ErrorBox message={(raw.error as Error).message} /> : null}
          </div>
        </Panel>
        <Panel title="Run Adapter">
          <div className="space-y-4">
            <p className="text-sm text-zinc-300">
              Scores the held-out credit test split with the AutoGluon model trained at backend startup.
            </p>
            <button
              type="button"
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending || !trainingReady}
              className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
            >
              <Play size={16} />
              {runMutation.isPending ? "Running" : "Run Credit Risk Model"}
            </button>
            {(runMutation.isPending || runProgress) && (
              <ProgressBar percent={runProgress?.progress_percent ?? 0} stage={runProgress?.stage ?? "starting"} />
            )}
            {trainingActive ? (
              <ProgressBar percent={training.data?.progress_percent ?? 0} stage={`Training: ${training.data?.stage ?? "…"}`} />
            ) : null}
            {training.data?.status === "failed" ? (
              <ErrorBox message={training.data.error ?? "Startup training failed."} />
            ) : null}
            {runMutation.isError ? <ErrorBox message={(runMutation.error as Error).message} /> : null}
            {latestTestRun ? <p className="text-sm text-zinc-400">Last test run: {latestTestRun.id}</p> : null}
          </div>
        </Panel>
      </div>
      <Panel title="Validation Metrics (startup training)">
        {valEvaluation ? (
          <EvaluationCharts evaluation={valEvaluation} mode="credit" />
        ) : trainingActive ? (
          <EmptyState text="Training in progress. Validation charts will appear when complete." />
        ) : (
          <EmptyState text="Validation metrics are not ready yet." />
        )}
      </Panel>
      <Panel title="Validation Decisions">
        {valEvaluation ? (
          <CreditRiskPredictionTable splitLabel="validation" rows={valPreview} evaluation={valEvaluation} />
        ) : (
          <EmptyState text="Validation decision table appears after startup training completes." />
        )}
      </Panel>
      <Panel title="Test Evaluation (Run Credit Risk Model)">
        {activeTestEvaluation ? (
          <EvaluationCharts evaluation={activeTestEvaluation} mode="credit" />
        ) : (
          <EmptyState text="Run the credit risk model to see held-out ROC-AUC, PR-AUC, precision/recall, and confusion matrix." />
        )}
      </Panel>
      <Panel title="Test Decisions">
        {!trainingReady ? (
          <EmptyState text="Available after startup training finishes. Run Credit Risk Model to score the test split." />
        ) : !activeTestEvaluation ? (
          <EmptyState text="Training is complete. Click Run Credit Risk Model to generate test decisions in this table." />
        ) : (
          <CreditRiskPredictionTable splitLabel="test" rows={testPreview} evaluation={activeTestEvaluation} />
        )}
      </Panel>
      <Panel title="Run History">
        <RunHistory runs={runs.data?.items ?? []} />
      </Panel>
    </section>
  );
}

function DocumentOcrPage() {
  const slug = "document-ocr";
  const queryClient = useQueryClient();
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);

  const raw = useQuery({ queryKey: ["raw", slug], queryFn: () => fetchRawData(slug) });
  const training = useStartupTraining(slug);
  const startupReady = training.data?.status === "completed";
  const startupActive = isStartupTrainingActive(training.data?.status);
  const aiHealth = useQuery({ queryKey: ["ai-health"], queryFn: fetchAiHealth });
  const runs = useQuery({ queryKey: ["runs", slug], queryFn: () => fetchRuns(slug) });
  const runInProgress = runs.data?.items.some((run) => run.status === "running") ?? false;
  const latest = useQuery({
    queryKey: ["document-ocr-latest"],
    queryFn: fetchDocumentOcrLatest,
    refetchInterval: () => (runInProgress || runProgress !== null ? 1000 : false)
  });

  const runMutation = useMutation({
    mutationFn: () =>
      runUseCaseWithProgress(
        slug,
        (progress) => {
          setRunProgress(progress);
        },
        "Document OCR run failed."
      ),
    onSuccess: () => {
      setRunProgress(null);
      queryClient.invalidateQueries({ queryKey: ["document-ocr-latest"] });
      queryClient.invalidateQueries({ queryKey: ["runs", slug] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    },
    onError: () => setRunProgress(null)
  });

  const rawDataset = raw.data?.datasets.find((dataset) => dataset.dataset_key === "manifest");
  const manifestPreview = rawDataset?.payload.preview ?? [];
  const artifacts = raw.data?.artifacts ?? [];
  const artifactGroups = groupDocumentArtifacts(artifacts);
  const mutationPayload = isDocumentOcrPayload(runMutation.data?.result.payload)
    ? runMutation.data.result.payload
    : null;
  const latestPayload = startupReady ? mutationPayload ?? latest.data?.latest?.payload ?? null : null;
  const documents = latestPayload?.documents ?? [];
  const latestRun = startupReady ? runMutation.data?.run ?? latest.data?.latest?.run ?? null : null;
  const selectedDocument =
    documents.find((document) => document.document_id === selectedDocumentId) ?? documents[0] ?? null;

  useEffect(() => {
    if (!documents.length) {
      setSelectedDocumentId(null);
      return;
    }
    if (!selectedDocumentId || !documents.some((document) => document.document_id === selectedDocumentId)) {
      setSelectedDocumentId(documents[0].document_id);
    }
  }, [documents, selectedDocumentId]);

  const localOcr = aiHealth.data?.adapters.find((adapter) => adapter.name === "Local OCR");
  const gptFallback = aiHealth.data?.adapters.find((adapter) => adapter.name === "OpenAI GPT-4o");

  return (
    <section className="space-y-6 p-8">
      <PageTitle
        icon={<FileText size={22} />}
        title="Document OCR"
        subtitle="Structured extraction from synthetic banking PDF, scanned PDF, and image packages with local OCR first and GPT-4o fallback for image-only documents."
      />

      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Customers" value={rawDataset?.payload.customer_count ?? 0} />
        <MetricCard label="Documents" value={rawDataset?.payload.document_count ?? 0} />
        <MetricCard label="Raw Artifacts" value={artifacts.length} />
        <MetricCard label="Latest Provider" value={formatProviderLabel(latestPayload?.summary.provider_used ?? latestRun?.provider_used)} />
      </div>

      <DocumentOcrOverviewPanel
        customerCount={rawDataset?.payload.customer_count ?? 0}
        documentCount={rawDataset?.payload.document_count ?? 0}
      />

      <div className="grid grid-cols-[1.1fr_0.9fr] gap-5">
        <Panel title="Raw Manifest Preview">
          <div className="space-y-3">
            <p className="text-sm text-zinc-400">
              Seeded manifest preview from the deterministic Banking Package dataset.
            </p>
            <DataTable rows={manifestPreview} limit={8} />
            {raw.isError ? <ErrorBox message={(raw.error as Error).message} /> : null}
          </div>
        </Panel>

        <Panel title="Adapter Health">
          <div className="space-y-3">
            <AdapterHealthRow adapter={localOcr} fallbackName="Local OCR" />
            <AdapterHealthRow adapter={gptFallback} fallbackName="OpenAI GPT-4o" />
            {aiHealth.isError ? <ErrorBox message={(aiHealth.error as Error).message} /> : null}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-[1fr_0.9fr] gap-5">
        <Panel title="Raw Artifacts By Customer">
          <div className="max-h-[420px] space-y-3 overflow-y-auto pr-2">
            {artifactGroups.customerGroups.map(([customerId, group]) => (
              <div key={customerId} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                <div className="flex items-center justify-between">
                  <p className="font-medium">{customerId}</p>
                  <span className="text-xs text-zinc-400">{group.length} files</span>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-zinc-400">
                  {group.map((artifact) => (
                    <div key={artifact.id} className="flex items-center gap-2">
                      <FileStack size={14} className="text-emerald-300" />
                      <span className="truncate">{artifact.file_name}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {artifactGroups.supportFiles.length ? (
              <div className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                <p className="font-medium">Manifest Files</p>
                <div className="mt-2 grid gap-2 text-xs text-zinc-400">
                  {artifactGroups.supportFiles.map((artifact) => (
                    <div key={artifact.id} className="flex items-center gap-2">
                      <FileStack size={14} className="text-emerald-300" />
                      <span>{artifact.file_name}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </Panel>

        <Panel title="Run Adapter">
          <div className="space-y-4">
            <p className="text-sm text-zinc-300">
              Runs pdfplumber and PyMuPDF locally for readable PDFs. Scanned PDFs and JPG notices use GPT-4o fallback when available.
            </p>
            <button
              type="button"
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending || !rawDataset || !startupReady}
              className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
            >
              <Play size={16} />
              {runMutation.isPending ? "Running" : "Run Document OCR"}
            </button>
            {(runMutation.isPending || runProgress) && (
              <ProgressBar percent={runProgress?.progress_percent ?? 0} stage={runProgress?.stage ?? "starting"} />
            )}
            {startupActive ? (
              <ProgressBar percent={training.data?.progress_percent ?? 0} stage={`Startup: ${training.data?.stage ?? "queued"}`} />
            ) : null}
            {training.data?.status === "failed" ? (
              <ErrorBox message={training.data.error ?? "Document OCR startup processing failed."} />
            ) : null}
            {runMutation.isError ? <ErrorBox message={(runMutation.error as Error).message} /> : null}
            {latestRun ? (
              <div className="rounded-md border border-zinc-800 bg-zinc-950 p-3 text-sm text-zinc-300">
                <p className="font-medium">{formatProviderLabel(latestRun.provider_used)}</p>
                <p className="mt-1 text-zinc-400">Last run: {latestRun.id}</p>
              </div>
            ) : (
              <EmptyState text="No OCR extraction run has been saved yet." />
            )}
          </div>
        </Panel>
      </div>

      <Panel title="Latest Extraction Summary">
        {latestPayload ? (
          <div className="grid grid-cols-6 gap-3">
            <MetricCard label="Provider" value={formatProviderLabel(latestPayload.summary.provider_used)} />
            <MetricCard label="Fallbacks" value={latestPayload.summary.fallback_count} />
            <MetricCard label="Field Accuracy" value={formatPercent(latestPayload.summary.field_accuracy)} />
            <MetricCard label="Table Recall" value={formatPercent(latestPayload.summary.table_row_recall)} />
            <MetricCard label="Avg Confidence" value={formatPercent(latestPayload.summary.average_confidence)} />
            <MetricCard label="Warnings" value={latestPayload.summary.warning_count} />
          </div>
        ) : (
          <EmptyState text="Run Document OCR to generate persisted extraction metrics." />
        )}
      </Panel>

      <div className="grid grid-cols-[1.15fr_0.85fr] gap-5">
        <Panel title="Document Results">
          {documents.length ? (
            <DocumentResultsTable
              documents={documents}
              selectedDocumentId={selectedDocument?.document_id ?? null}
              onSelect={setSelectedDocumentId}
            />
          ) : (
            <EmptyState text="Run Document OCR to populate extracted document rows." />
          )}
        </Panel>

        <Panel title="Selected Document Detail">
          {selectedDocument ? (
            <DocumentDetail document={selectedDocument} />
          ) : (
            <EmptyState text="Select a document after an OCR run completes." />
          )}
        </Panel>
      </div>

      <Panel title="Run History">
        <RunHistory runs={runs.data?.items ?? []} />
      </Panel>
    </section>
  );
}

function SupportChatbotPage() {
  const slug = "support-chatbot";
  const queryClient = useQueryClient();
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);
  const [question, setQuestion] = useState("What should an agent do when a customer reports an unauthorized card transaction?");
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);

  const raw = useQuery({ queryKey: ["raw", slug], queryFn: () => fetchRawData(slug) });
  const training = useStartupTraining(slug);
  const startupReady = training.data?.status === "completed";
  const startupActive = isStartupTrainingActive(training.data?.status);
  const aiHealth = useQuery({ queryKey: ["ai-health"], queryFn: fetchAiHealth });
  const runs = useQuery({ queryKey: ["runs", slug], queryFn: () => fetchRuns(slug) });
  const runInProgress = runs.data?.items.some((run) => run.status === "running") ?? false;
  const latest = useQuery({
    queryKey: ["support-chatbot-latest"],
    queryFn: fetchSupportChatbotLatest,
    refetchInterval: () => (runInProgress || runProgress !== null ? 1000 : false)
  });

  const evalMutation = useMutation({
    mutationFn: () =>
      runUseCaseWithProgress(
        slug,
        (progress) => {
          setRunProgress(progress);
        },
        "Support evaluation failed."
      ),
    onSuccess: () => {
      setRunProgress(null);
      queryClient.invalidateQueries({ queryKey: ["support-chatbot-latest"] });
      queryClient.invalidateQueries({ queryKey: ["runs", slug] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    },
    onError: () => setRunProgress(null)
  });

  const chatMutation = useMutation({
    mutationFn: () => submitSupportChatbotQuestion({ question }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["support-chatbot-latest"] });
      queryClient.invalidateQueries({ queryKey: ["runs", slug] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    }
  });

  const rawDataset = raw.data?.datasets.find((dataset) => dataset.dataset_key === "knowledge_base");
  const artifacts = raw.data?.artifacts ?? [];
  const artifactGroups = groupSupportArtifacts(artifacts);
  const evaluationPayload = isSupportChatbotPayload(evalMutation.data?.result.payload)
    ? evalMutation.data.result.payload
    : startupReady
      ? latest.data?.latest?.payload ?? null
      : null;
  const chatPayload = startupReady ? chatMutation.data?.payload ?? latest.data?.latest_chat?.payload ?? null : null;
  const activePayload = chatPayload ?? evaluationPayload;
  const activeAnswer = chatPayload?.answers[0] ?? evaluationPayload?.answers[0] ?? null;
  const selectedChunk =
    activePayload?.retrieved_chunks.find((chunk) => chunk.chunk_id === selectedChunkId) ??
    activePayload?.retrieved_chunks.find((chunk) => activeAnswer?.sources.some((source) => source.chunk_id === chunk.chunk_id)) ??
    activePayload?.retrieved_chunks[0] ??
    null;
  const localLlm = aiHealth.data?.adapters.find((adapter) => adapter.name === "Ollama Qwen");
  const gptFallback = aiHealth.data?.adapters.find((adapter) => adapter.name === "OpenAI GPT-4o");
  const latestProvider = startupReady
    ? chatPayload?.summary.provider_used ?? evaluationPayload?.summary.provider_used ?? latest.data?.latest_chat?.run.provider_used ?? latest.data?.latest?.run.provider_used
    : undefined;

  useEffect(() => {
    if (selectedChunkId && activePayload?.retrieved_chunks.some((chunk) => chunk.chunk_id === selectedChunkId)) {
      return;
    }
    const firstSourceChunk = activeAnswer?.sources[0]?.chunk_id;
    if (firstSourceChunk) {
      setSelectedChunkId(firstSourceChunk);
    }
  }, [activeAnswer, activePayload, selectedChunkId]);

  return (
    <section className="space-y-6 p-8">
      <PageTitle
        icon={<MessageSquare size={22} />}
        title="Support Chatbot"
        subtitle="Local-first RAG assistant for synthetic branch and contact-center support policies, with Ollama Qwen and GPT-4o fallback."
      />

      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Knowledge Documents" value={rawDataset?.payload.knowledge_document_count ?? 0} />
        <MetricCard label="Chunks" value={rawDataset?.payload.chunk_count ?? 0} />
        <MetricCard label="Evaluation Questions" value={rawDataset?.payload.evaluation_question_count ?? 0} />
        <MetricCard label="Latest Provider" value={formatProviderLabel(latestProvider)} />
      </div>

      <SupportChatbotOverviewPanel />

      <div className="grid grid-cols-[1.1fr_0.9fr] gap-5">
        <Panel title="Raw Knowledge Base">
          <div className="space-y-4">
            <DataTable rows={rawDataset?.payload.preview ?? []} limit={8} />
            <div className="grid grid-cols-2 gap-3">
              {artifactGroups.map(([group, groupArtifacts]) => (
                <div key={group} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{formatDocumentType(group)}</p>
                    <span className="text-xs text-zinc-400">{groupArtifacts.length} files</span>
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-zinc-400">
                    {groupArtifacts.map((artifact) => (
                      <div key={artifact.id} className="flex items-center gap-2">
                        <FileStack size={14} className="text-emerald-300" />
                        <span className="truncate">{artifact.file_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            {raw.isError ? <ErrorBox message={(raw.error as Error).message} /> : null}
          </div>
        </Panel>

        <Panel title="Adapter Health">
          <div className="space-y-3">
            <AdapterHealthRow adapter={localLlm} fallbackName="Ollama Qwen" />
            <AdapterHealthRow adapter={gptFallback} fallbackName="OpenAI GPT-4o" />
            {aiHealth.isError ? <ErrorBox message={(aiHealth.error as Error).message} /> : null}
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-[1fr_0.9fr] gap-5">
        <Panel title="Chat Workspace">
          <div className="space-y-4">
            <label className="block text-sm font-medium text-zinc-300" htmlFor="support-chat-question">
              Agent question
            </label>
            <textarea
              id="support-chat-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              rows={4}
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 p-3 text-sm text-zinc-100 outline-none ring-emerald-500/40 focus:ring-2"
            />
            <button
              type="button"
              onClick={() => chatMutation.mutate()}
              disabled={chatMutation.isPending || question.trim().length < 3 || !rawDataset || !startupReady}
              className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
            >
              <Send size={16} />
              {chatMutation.isPending ? "Asking" : "Ask Support Chatbot"}
            </button>
            {chatMutation.isError ? <ErrorBox message={(chatMutation.error as Error).message} /> : null}
            {startupActive ? (
              <ProgressBar percent={training.data?.progress_percent ?? 0} stage={`Startup: ${training.data?.stage ?? "queued"}`} />
            ) : null}
            {training.data?.status === "failed" ? (
              <ErrorBox message={training.data.error ?? "Support Chatbot startup evaluation failed."} />
            ) : null}
            {chatPayload?.answers[0] ? (
              <SupportAnswerCard answer={chatPayload.answers[0]} onSelectSource={setSelectedChunkId} />
            ) : (
              <EmptyState text="Ask a support question to generate a persisted answer with citations." />
            )}
          </div>
        </Panel>

        <Panel title="Source Detail">
          {selectedChunk ? (
            <SupportSourceDetail chunk={selectedChunk} />
          ) : (
            <EmptyState text="Ask a question or run the evaluation to inspect retrieved source chunks." />
          )}
        </Panel>
      </div>

      <Panel title="Evaluation Runner">
        <div className="space-y-4">
          <button
            type="button"
            onClick={() => evalMutation.mutate()}
            disabled={evalMutation.isPending || !rawDataset || !startupReady}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
          >
            <Play size={16} />
            {evalMutation.isPending ? "Running" : "Run Support Evaluation"}
          </button>
          {(evalMutation.isPending || runProgress) && (
            <ProgressBar percent={runProgress?.progress_percent ?? 0} stage={runProgress?.stage ?? "starting"} />
          )}
          {startupActive ? (
            <ProgressBar percent={training.data?.progress_percent ?? 0} stage={`Startup: ${training.data?.stage ?? "queued"}`} />
          ) : null}
          {evalMutation.isError ? <ErrorBox message={(evalMutation.error as Error).message} /> : null}
          {evaluationPayload ? (
            <div className="space-y-4">
              <div className="grid grid-cols-6 gap-3">
                <MetricCard label="Provider" value={formatProviderLabel(evaluationPayload.summary.provider_used)} />
                <MetricCard label="Answered" value={`${evaluationPayload.summary.answered_count}/${evaluationPayload.summary.question_count}`} />
                <MetricCard label="Citation Accuracy" value={formatPercent(evaluationPayload.summary.citation_accuracy)} />
                <MetricCard label="Source Recall" value={formatPercent(evaluationPayload.summary.source_recall)} />
                <MetricCard label="Avg Confidence" value={formatPercent(evaluationPayload.summary.average_confidence)} />
                <MetricCard label="Fallbacks" value={evaluationPayload.summary.fallback_count} />
              </div>
              <SupportEvaluationTable answers={evaluationPayload.answers} onSelectSource={setSelectedChunkId} />
            </div>
          ) : (
            <EmptyState text="Run the deterministic support evaluation set to see answer quality and citation metrics." />
          )}
        </div>
      </Panel>

      <Panel title="Run History">
        <RunHistory runs={runs.data?.items ?? []} />
      </Panel>
    </section>
  );
}

function LiquidityForecastPage() {
  const slug = "liquidity-forecast";
  const queryClient = useQueryClient();
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);
  const [selectedSeriesId, setSelectedSeriesId] = useState<string | null>(null);

  const raw = useQuery({ queryKey: ["raw", slug], queryFn: () => fetchRawData(slug) });
  const training = useStartupTraining(slug);
  const startupReady = training.data?.status === "completed";
  const startupActive = isStartupTrainingActive(training.data?.status);
  const aiHealth = useQuery({ queryKey: ["ai-health"], queryFn: fetchAiHealth });
  const runs = useQuery({ queryKey: ["runs", slug], queryFn: () => fetchRuns(slug) });
  const runInProgress = runs.data?.items.some((run) => run.status === "running") ?? false;
  const latest = useQuery({
    queryKey: ["liquidity-forecast-latest"],
    queryFn: fetchLiquidityForecastLatest,
    refetchInterval: () => (runInProgress || runProgress !== null ? 1000 : false)
  });

  const runMutation = useMutation({
    mutationFn: () =>
      runUseCaseWithProgress(
        slug,
        (progress) => {
          setRunProgress(progress);
        },
        "Liquidity forecast run failed."
      ),
    onSuccess: () => {
      setRunProgress(null);
      queryClient.invalidateQueries({ queryKey: ["liquidity-forecast-latest"] });
      queryClient.invalidateQueries({ queryKey: ["runs", slug] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    },
    onError: () => setRunProgress(null)
  });

  const rawDataset = raw.data?.datasets.find((dataset) => dataset.dataset_key === "cash_timeseries");
  const artifacts = raw.data?.artifacts ?? [];
  const artifactGroups = groupLiquidityArtifacts(artifacts);
  const payload = isLiquidityForecastPayload(runMutation.data?.result.payload)
    ? runMutation.data.result.payload
    : startupReady
      ? latest.data?.latest?.payload ?? null
      : null;
  const profiles = payload?.series_profiles ?? [];
  const selectedProfile = profiles.find((profile) => profile.series_id === selectedSeriesId) ?? profiles[0] ?? null;
  const selectedForecasts = selectedProfile
    ? payload?.forecasts.filter((forecast) => forecast.series_id === selectedProfile.series_id) ?? []
    : [];
  const timeSeriesAdapter = aiHealth.data?.adapters.find((adapter) => adapter.name === "AutoGluon TimeSeries");
  const latestProvider = startupReady ? payload?.summary.provider_used ?? latest.data?.latest?.run.provider_used : undefined;

  useEffect(() => {
    if (selectedSeriesId && profiles.some((profile) => profile.series_id === selectedSeriesId)) {
      return;
    }
    if (profiles[0]?.series_id) {
      setSelectedSeriesId(profiles[0].series_id);
    }
  }, [profiles, selectedSeriesId]);

  return (
    <section className="space-y-6 p-8">
      <PageTitle
        icon={<Activity size={22} />}
        title="Liquidity Forecast"
        subtitle="Branch and ATM cash-demand forecasting with quantiles, stockout risk, and replenishment recommendations."
      />

      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="Locations" value={rawDataset?.payload.location_count ?? 0} />
        <MetricCard label="History Days" value={rawDataset?.payload.history_days ?? 0} />
        <MetricCard label="Forecast Horizon" value={`${rawDataset?.payload.forecast_horizon_days ?? 0} days`} />
        <MetricCard label="Latest Provider" value={formatProviderLabel(latestProvider)} />
      </div>

      <LiquidityOverviewPanel />

      <div className="grid grid-cols-[1.15fr_0.85fr] gap-5">
        <Panel title="Raw Cash Data">
          <div className="space-y-4">
            <DataTable rows={rawDataset?.payload.preview ?? []} limit={8} />
            <div className="grid grid-cols-3 gap-3">
              <MetricCard label="History Records" value={rawDataset?.payload.history_record_count ?? 0} />
              <MetricCard label="Holdout Actuals" value={rawDataset?.payload.holdout_record_count ?? 0} />
              <MetricCard label="Calendar Events" value={rawDataset?.payload.calendar_event_count ?? 0} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {artifactGroups.map(([group, groupArtifacts]) => (
                <div key={group} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{formatDocumentType(group)}</p>
                    <span className="text-xs text-zinc-400">{groupArtifacts.length} files</span>
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-zinc-400">
                    {groupArtifacts.map((artifact) => (
                      <div key={artifact.id} className="flex items-center gap-2">
                        <FileStack size={14} className="text-emerald-300" />
                        <span className="truncate">{artifact.file_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            {raw.isError ? <ErrorBox message={(raw.error as Error).message} /> : null}
          </div>
        </Panel>

        <Panel title="Adapter Health">
          <div className="space-y-3">
            <AdapterHealthRow adapter={timeSeriesAdapter} fallbackName="AutoGluon TimeSeries" />
            <div className="rounded-md border border-zinc-800 bg-zinc-950 p-3 text-sm text-zinc-400">
              <p className="font-medium text-zinc-100">Seasonal Baseline</p>
              <p className="mt-1">
                Local deterministic day-of-week baseline is always available for this synthetic MVP.
              </p>
            </div>
            {aiHealth.isError ? <ErrorBox message={(aiHealth.error as Error).message} /> : null}
          </div>
        </Panel>
      </div>

      <Panel title="Run Forecast">
        <div className="space-y-4">
          <button
            type="button"
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || !rawDataset || !startupReady}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
          >
            <Play size={16} />
            {runMutation.isPending ? "Running" : "Run Liquidity Forecast"}
          </button>
          {(runMutation.isPending || runProgress) && (
            <ProgressBar percent={runProgress?.progress_percent ?? 0} stage={runProgress?.stage ?? "starting"} />
          )}
          {startupActive ? (
            <ProgressBar percent={training.data?.progress_percent ?? 0} stage={`Startup: ${training.data?.stage ?? "queued"}`} />
          ) : null}
          {training.data?.status === "failed" ? (
            <ErrorBox message={training.data.error ?? "Liquidity Forecast startup processing failed."} />
          ) : null}
          {runMutation.isError ? <ErrorBox message={(runMutation.error as Error).message} /> : null}
          {payload ? (
            <div className="space-y-4">
              <div className="grid grid-cols-6 gap-3">
                <MetricCard label="Provider" value={formatProviderLabel(payload.summary.provider_used)} />
                <MetricCard label="MAE" value={formatMoney(payload.summary.mae)} />
                <MetricCard label="RMSE" value={formatMoney(payload.summary.rmse)} />
                <MetricCard label="MAPE" value={formatPercent(payload.summary.mape)} />
                <MetricCard label="Coverage" value={formatPercent(payload.summary.p10_p90_coverage)} />
                <MetricCard label="High Risk Days" value={payload.summary.high_risk_forecast_count} />
              </div>
              <div className="grid grid-cols-4 gap-3">
                <MetricCard label="Avg Stockout Risk" value={formatPercent(payload.summary.average_stockout_risk)} />
                <MetricCard label="Recommended Cash" value={formatMoney(payload.summary.recommended_replenishment_total)} />
                <MetricCard label="Forecast Rows" value={payload.summary.forecast_count} />
                <MetricCard label="Fallbacks" value={payload.summary.fallback_count} />
              </div>
              {payload.warnings.length ? (
                <div className="space-y-2">
                  {payload.warnings.map((warning) => (
                    <ErrorBox key={warning} message={warning} />
                  ))}
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState text="Run Liquidity Forecast to create quantile forecasts and replenishment recommendations." />
          )}
        </div>
      </Panel>

      <div className="grid grid-cols-[1.2fr_0.8fr] gap-5">
        <Panel title="Forecast Chart">
          {payload && selectedProfile ? (
            <div className="space-y-4">
              <SeriesSelector profiles={profiles} selectedSeriesId={selectedProfile.series_id} onSelect={setSelectedSeriesId} />
              <LiquidityForecastChart forecasts={selectedForecasts} />
            </div>
          ) : (
            <EmptyState text="Forecast chart appears after the first run." />
          )}
        </Panel>

        <Panel title="Series Detail">
          {selectedProfile ? (
            <LiquiditySeriesDetail profile={selectedProfile} forecasts={selectedForecasts} />
          ) : (
            <EmptyState text="Select a series after a forecast run." />
          )}
        </Panel>
      </div>

      <Panel title="Forecast Table">
        {payload ? (
          <LiquidityForecastTable forecasts={payload.forecasts} onSelectSeries={setSelectedSeriesId} />
        ) : (
          <EmptyState text="Forecast rows will be stored and displayed after a run completes." />
        )}
      </Panel>

      <Panel title="Calendar Events">
        <DataTable rows={rawDataset?.payload.calendar_preview ?? []} limit={12} />
      </Panel>

      <Panel title="Run History">
        <RunHistory runs={runs.data?.items ?? []} />
      </Panel>
    </section>
  );
}

function AmlMonitoringPage() {
  const slug = "aml-monitoring";
  const queryClient = useQueryClient();
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);

  const raw = useQuery({ queryKey: ["raw", slug], queryFn: () => fetchRawData(slug) });
  const training = useStartupTraining(slug);
  const startupReady = training.data?.status === "completed";
  const startupActive = isStartupTrainingActive(training.data?.status);
  const aiHealth = useQuery({ queryKey: ["ai-health"], queryFn: fetchAiHealth });
  const runs = useQuery({ queryKey: ["runs", slug], queryFn: () => fetchRuns(slug) });
  const runInProgress = runs.data?.items.some((run) => run.status === "running") ?? false;
  const latest = useQuery({
    queryKey: ["aml-monitoring-latest"],
    queryFn: fetchAmlMonitoringLatest,
    refetchInterval: () => (runInProgress || runProgress !== null ? 1000 : false)
  });

  const runMutation = useMutation({
    mutationFn: () =>
      runUseCaseWithProgress(
        slug,
        (progress) => {
          setRunProgress(progress);
        },
        "AML Monitoring run failed."
      ),
    onSuccess: () => {
      setRunProgress(null);
      queryClient.invalidateQueries({ queryKey: ["aml-monitoring-latest"] });
      queryClient.invalidateQueries({ queryKey: ["runs", slug] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    },
    onError: () => setRunProgress(null)
  });

  const trainDataset = raw.data?.datasets.find((dataset) => dataset.dataset_key === "train");
  const valDataset = raw.data?.datasets.find((dataset) => dataset.dataset_key === "val");
  const testDataset = raw.data?.datasets.find((dataset) => dataset.dataset_key === "test");
  const valPreview = valDataset?.payload.preview ?? valDataset?.payload.records ?? [];
  const testPreview = testDataset?.payload.preview ?? testDataset?.payload.records ?? [];
  const artifacts = raw.data?.artifacts ?? [];
  const artifactGroups = groupAmlArtifacts(artifacts);
  const mutationPayload = isAmlMonitoringPayload(runMutation.data?.result.payload)
    ? runMutation.data.result.payload
    : null;
  const validationPayload = startupReady ? latest.data?.val?.payload ?? null : null;
  const testPayload = startupReady ? mutationPayload ?? latest.data?.test?.payload ?? null : null;
  const activePayload = testPayload ?? validationPayload;
  const activeAlerts = activePayload?.alerts ?? [];
  const selectedAlert =
    activeAlerts.find((alert) => alert.alert_id === selectedAlertId) ?? activeAlerts[0] ?? null;
  const selectedNarrative =
    activePayload?.narratives.find((narrative) => narrative.alert_id === selectedAlert?.alert_id) ?? null;
  const tabularAdapter = aiHealth.data?.adapters.find((adapter) => adapter.name === "AutoGluon Tabular");
  const localLlm = aiHealth.data?.adapters.find((adapter) => adapter.name === "Ollama Qwen");
  const gptFallback = aiHealth.data?.adapters.find((adapter) => adapter.name === "OpenAI GPT-4o");
  const latestProvider = startupReady
    ? testPayload?.summary.provider_used ?? validationPayload?.summary.provider_used ?? latest.data?.val?.run.provider_used
    : undefined;
  const totalSarLabels = Number(trainDataset?.payload.label_count ?? 0) + Number(valDataset?.payload.label_count ?? 0) + Number(testDataset?.payload.label_count ?? 0);

  useEffect(() => {
    if (selectedAlertId && activeAlerts.some((alert) => alert.alert_id === selectedAlertId)) {
      return;
    }
    if (activeAlerts[0]?.alert_id) {
      setSelectedAlertId(activeAlerts[0].alert_id);
    }
  }, [activeAlerts, selectedAlertId]);

  return (
    <section className="space-y-6 p-8">
      <PageTitle
        icon={<ShieldCheck size={22} />}
        title="AML Monitoring"
        subtitle="Synthetic AML alert prioritization with AutoGluon scoring, network enrichment, and SAR narrative drafts through local LLM or GPT-4o fallback."
      />

      <div className="grid grid-cols-5 gap-4">
        <MetricCard label="Train Alerts" value={trainDataset?.payload.record_count ?? 0} />
        <MetricCard label="Val Alerts" value={valDataset?.payload.record_count ?? 0} />
        <MetricCard label="Test Alerts" value={testDataset?.payload.record_count ?? 0} />
        <MetricCard label="SAR Labels" value={totalSarLabels} />
        <MetricCard label="Startup Status" value={training.data?.status ?? "loading"} />
      </div>

      <AmlOverviewPanel />

      <div className="grid grid-cols-[1.15fr_0.85fr] gap-5">
        <Panel title="Raw AML Data">
          <div className="space-y-4">
            <DataTable rows={valPreview} limit={8} />
            <div className="grid grid-cols-2 gap-3">
              {artifactGroups.map(([group, groupArtifacts]) => (
                <div key={group} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{formatDocumentType(group)}</p>
                    <span className="text-xs text-zinc-400">{groupArtifacts.length} files</span>
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-zinc-400">
                    {groupArtifacts.map((artifact) => (
                      <div key={artifact.id} className="flex items-center gap-2">
                        <FileStack size={14} className="text-emerald-300" />
                        <span className="truncate">{artifact.file_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            {raw.isError ? <ErrorBox message={(raw.error as Error).message} /> : null}
          </div>
        </Panel>

        <Panel title="Adapter Health">
          <div className="space-y-3">
            <AdapterHealthRow adapter={tabularAdapter} fallbackName="AutoGluon Tabular" />
            <AdapterHealthRow adapter={localLlm} fallbackName="Ollama Qwen" />
            <AdapterHealthRow adapter={gptFallback} fallbackName="OpenAI GPT-4o" />
            {aiHealth.isError ? <ErrorBox message={(aiHealth.error as Error).message} /> : null}
          </div>
        </Panel>
      </div>

      <Panel title="Run AML Monitoring">
        <div className="space-y-4">
          <p className="text-sm text-zinc-300">
            Startup trains and validates the AML model. The run button scores the held-out test split and drafts narratives for the highest-risk alerts.
          </p>
          <button
            type="button"
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || !testDataset || !startupReady}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
          >
            <Play size={16} />
            {runMutation.isPending ? "Running" : "Run AML Monitoring"}
          </button>
          {(runMutation.isPending || runProgress) && (
            <ProgressBar percent={runProgress?.progress_percent ?? 0} stage={runProgress?.stage ?? "starting"} />
          )}
          {startupActive ? (
            <ProgressBar percent={training.data?.progress_percent ?? 0} stage={`Startup: ${training.data?.stage ?? "queued"}`} />
          ) : null}
          {training.data?.status === "failed" ? (
            <ErrorBox message={training.data.error ?? "AML Monitoring startup processing failed."} />
          ) : null}
          {runMutation.isError ? <ErrorBox message={(runMutation.error as Error).message} /> : null}
          {activePayload ? (
            <div className="grid grid-cols-6 gap-3">
              <MetricCard label="Provider" value={formatProviderLabel(latestProvider ?? activePayload.summary.provider_used)} />
              <MetricCard label="PR-AUC" value={activePayload.summary.primary_score != null ? activePayload.summary.primary_score.toFixed(3) : "N/A"} />
              <MetricCard label="Recall" value={formatPercent(activePayload.summary.recall)} />
              <MetricCard label="F1" value={activePayload.summary.f1.toFixed(3)} />
              <MetricCard label="High Risk" value={activePayload.summary.high_risk_count} />
              <MetricCard label="Fallbacks" value={activePayload.summary.fallback_count} />
            </div>
          ) : (
            <EmptyState text="Startup validation metrics will appear when the AML stage completes." />
          )}
        </div>
      </Panel>

      <Panel title="Validation Metrics (startup training)">
        {validationPayload ? (
          <EvaluationCharts evaluation={validationPayload.evaluation} />
        ) : startupActive ? (
          <EmptyState text="AML startup processing is running. Validation metrics will appear when complete." />
        ) : (
          <EmptyState text="Validation metrics are not ready yet." />
        )}
      </Panel>

      <div className="grid grid-cols-[1.15fr_0.85fr] gap-5">
        <Panel title={testPayload ? "Held-Out Test Alert Queue" : "Validation Alert Queue"}>
          {activeAlerts.length ? (
            <AmlAlertQueue alerts={activeAlerts} selectedAlertId={selectedAlert?.alert_id ?? null} onSelect={setSelectedAlertId} />
          ) : (
            <EmptyState text="Alert queue appears after AML startup validation completes." />
          )}
        </Panel>

        <Panel title="Selected Alert Detail">
          {selectedAlert ? (
            <AmlAlertDetail alert={selectedAlert} narrative={selectedNarrative} />
          ) : (
            <EmptyState text="Select an alert after a validation or test run completes." />
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-[0.9fr_1.1fr] gap-5">
        <Panel title="Network Summary">
          {activePayload?.network_summary ? (
            <AmlNetworkSummaryPanel payload={activePayload} />
          ) : (
            <EmptyState text="Network summary is saved with AML results." />
          )}
        </Panel>

        <Panel title="Test Evaluation">
          {testPayload ? (
            <div className="space-y-4">
              <EvaluationCharts evaluation={testPayload.evaluation} />
              <DataTable rows={testPreview} limit={6} />
            </div>
          ) : (
            <EmptyState text="Run AML Monitoring after startup completion to score the held-out test alerts." />
          )}
        </Panel>
      </div>

      <Panel title="Run History">
        <RunHistory runs={runs.data?.items ?? []} />
      </Panel>
    </section>
  );
}

function KycKybPage() {
  const slug = "kyc-kyb";
  const queryClient = useQueryClient();
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null);

  const raw = useQuery({ queryKey: ["raw", slug], queryFn: () => fetchRawData(slug) });
  const training = useStartupTraining(slug);
  const startupReady = training.data?.status === "completed";
  const startupActive = isStartupTrainingActive(training.data?.status);
  const aiHealth = useQuery({ queryKey: ["ai-health"], queryFn: fetchAiHealth });
  const runs = useQuery({ queryKey: ["runs", slug], queryFn: () => fetchRuns(slug) });
  const runInProgress = runs.data?.items.some((run) => run.status === "running") ?? false;
  const latest = useQuery({
    queryKey: ["kyc-kyb-latest"],
    queryFn: fetchKycKybLatest,
    refetchInterval: () => (runInProgress || runProgress !== null ? 1000 : false)
  });

  const runMutation = useMutation({
    mutationFn: () =>
      runUseCaseWithProgress(
        slug,
        (progress) => {
          setRunProgress(progress);
        },
        "KYC/KYB verification run failed."
      ),
    onSuccess: () => {
      setRunProgress(null);
      queryClient.invalidateQueries({ queryKey: ["kyc-kyb-latest"] });
      queryClient.invalidateQueries({ queryKey: ["runs", slug] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    },
    onError: () => setRunProgress(null)
  });

  const individualDataset = raw.data?.datasets.find((dataset) => dataset.dataset_key === "individual_packages");
  const businessDataset = raw.data?.datasets.find((dataset) => dataset.dataset_key === "business_packages");
  const individualPreview = individualDataset?.payload.preview ?? individualDataset?.payload.records ?? [];
  const businessPreview = businessDataset?.payload.preview ?? businessDataset?.payload.records ?? [];
  const artifacts = raw.data?.artifacts ?? [];
  const artifactGroups = groupKycKybArtifacts(artifacts);
  const mutationPayload = isKycKybPayload(runMutation.data?.result.payload)
    ? runMutation.data.result.payload
    : null;
  const validationPayload = startupReady ? latest.data?.val?.payload ?? null : null;
  const testPayload = startupReady ? mutationPayload ?? latest.data?.test?.payload ?? null : null;
  const activePayload = testPayload ?? validationPayload;
  const activeDecisions = activePayload?.risk_decisions ?? [];
  const selectedDecision =
    activeDecisions.find((decision) => decision.package_id === selectedPackageId) ?? activeDecisions[0] ?? null;
  const selectedDocuments =
    activePayload?.extracted_documents.filter((document) => document.package_id === selectedDecision?.package_id) ?? [];
  const selectedFindings =
    activePayload?.rule_findings.filter((finding) => finding.package_id === selectedDecision?.package_id) ?? [];
  const localOcr = aiHealth.data?.adapters.find((adapter) => adapter.name === "Local OCR");
  const tabularAdapter = aiHealth.data?.adapters.find((adapter) => adapter.name === "AutoGluon Tabular");
  const gptFallback = aiHealth.data?.adapters.find((adapter) => adapter.name === "OpenAI GPT-4o");
  const latestProvider = startupReady
    ? testPayload?.summary.provider_used ?? validationPayload?.summary.provider_used ?? latest.data?.val?.run.provider_used
    : undefined;
  const manualReviewLabels =
    Number(individualDataset?.payload.manual_review_label_count ?? 0) +
    Number(businessDataset?.payload.manual_review_label_count ?? 0);
  const rawArtifactCount = artifacts.length;

  useEffect(() => {
    if (selectedPackageId && activeDecisions.some((decision) => decision.package_id === selectedPackageId)) {
      return;
    }
    if (activeDecisions[0]?.package_id) {
      setSelectedPackageId(activeDecisions[0].package_id);
    }
  }, [activeDecisions, selectedPackageId]);

  return (
    <section className="space-y-6 p-8">
      <PageTitle
        icon={<Landmark size={22} />}
        title="KYC/KYB"
        subtitle="Synthetic retail and business onboarding verification with local extraction, deterministic policy rules, AutoGluon risk scoring, and GPT-4o fallback for image-only artifacts."
      />

      <div className="grid grid-cols-5 gap-4">
        <MetricCard label="Individual Packages" value={individualDataset?.payload.package_count ?? 0} />
        <MetricCard label="Business Packages" value={businessDataset?.payload.package_count ?? 0} />
        <MetricCard label="Raw Artifacts" value={rawArtifactCount} />
        <MetricCard label="Manual Review Labels" value={manualReviewLabels} />
        <MetricCard label="Startup Status" value={training.data?.status ?? "loading"} />
      </div>

      <KycKybOverviewPanel />

      <div className="grid grid-cols-[1.15fr_0.85fr] gap-5">
        <Panel title="Raw Onboarding Packages">
          <div className="space-y-4">
            <DataTable rows={[...individualPreview.slice(0, 6), ...businessPreview.slice(0, 6)]} limit={12} />
            <div className="grid grid-cols-2 gap-3">
              {artifactGroups.map(([group, groupArtifacts]) => (
                <div key={group} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{formatDocumentType(group)}</p>
                    <span className="text-xs text-zinc-400">{groupArtifacts.length} files</span>
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-zinc-400">
                    {groupArtifacts.slice(0, 8).map((artifact) => (
                      <div key={artifact.id} className="flex items-center gap-2">
                        <FileStack size={14} className="text-emerald-300" />
                        <span className="truncate">{artifact.file_name}</span>
                      </div>
                    ))}
                    {groupArtifacts.length > 8 ? <p className="text-zinc-500">+{groupArtifacts.length - 8} more files</p> : null}
                  </div>
                </div>
              ))}
            </div>
            {raw.isError ? <ErrorBox message={(raw.error as Error).message} /> : null}
          </div>
        </Panel>

        <Panel title="Adapter Health">
          <div className="space-y-3">
            <AdapterHealthRow adapter={localOcr} fallbackName="Local OCR" />
            <AdapterHealthRow adapter={tabularAdapter} fallbackName="AutoGluon Tabular" />
            <AdapterHealthRow adapter={gptFallback} fallbackName="OpenAI GPT-4o" />
            {aiHealth.isError ? <ErrorBox message={(aiHealth.error as Error).message} /> : null}
          </div>
        </Panel>
      </div>

      <Panel title="Run KYC/KYB Verification">
        <div className="space-y-4">
          <p className="text-sm text-zinc-300">
            Startup trains and validates the onboarding model. The run button scores held-out synthetic packages and persists final verification decisions.
          </p>
          <button
            type="button"
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || !individualDataset || !businessDataset || !startupReady}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
          >
            <Play size={16} />
            {runMutation.isPending ? "Running" : "Run KYC/KYB Verification"}
          </button>
          {(runMutation.isPending || runProgress) && (
            <ProgressBar percent={runProgress?.progress_percent ?? 0} stage={runProgress?.stage ?? "starting"} />
          )}
          {startupActive ? (
            <ProgressBar percent={training.data?.progress_percent ?? 0} stage={`Startup: ${training.data?.stage ?? "queued"}`} />
          ) : null}
          {training.data?.status === "failed" ? (
            <ErrorBox message={training.data.error ?? "KYC/KYB startup processing failed."} />
          ) : null}
          {runMutation.isError ? <ErrorBox message={(runMutation.error as Error).message} /> : null}
          {activePayload ? (
            <div className="grid grid-cols-6 gap-3">
              <MetricCard label="Provider" value={formatProviderLabel(latestProvider ?? activePayload.summary.provider_used)} />
              <MetricCard label="PR-AUC" value={activePayload.summary.primary_score != null ? activePayload.summary.primary_score.toFixed(3) : "N/A"} />
              <MetricCard label="Recall" value={formatPercent(activePayload.summary.recall)} />
              <MetricCard label="F1" value={activePayload.summary.f1.toFixed(3)} />
              <MetricCard label="Rejected" value={activePayload.summary.rejected_count} />
              <MetricCard label="Fallbacks" value={activePayload.summary.fallback_count} />
            </div>
          ) : (
            <EmptyState text="Startup validation metrics will appear when the KYC/KYB stage completes." />
          )}
        </div>
      </Panel>

      <Panel title="Validation Metrics (startup training)">
        {validationPayload ? (
          <EvaluationCharts evaluation={validationPayload.evaluation} />
        ) : startupActive ? (
          <EmptyState text="KYC/KYB startup processing is running. Validation metrics will appear when complete." />
        ) : (
          <EmptyState text="Validation metrics are not ready yet." />
        )}
      </Panel>

      <div className="grid grid-cols-[1.15fr_0.85fr] gap-5">
        <Panel title={testPayload ? "Held-Out Test Package Queue" : "Validation Package Queue"}>
          {activeDecisions.length ? (
            <KycKybPackageQueue decisions={activeDecisions} selectedPackageId={selectedDecision?.package_id ?? null} onSelect={setSelectedPackageId} />
          ) : (
            <EmptyState text="Package decisions appear after KYC/KYB startup validation completes." />
          )}
        </Panel>

        <Panel title="Selected Package Detail">
          {selectedDecision ? (
            <KycKybPackageDetail decision={selectedDecision} documents={selectedDocuments} findings={selectedFindings} />
          ) : (
            <EmptyState text="Select a package after validation or test scoring completes." />
          )}
        </Panel>
      </div>

      <Panel title="Test Evaluation">
        {testPayload ? (
          <EvaluationCharts evaluation={testPayload.evaluation} />
        ) : (
          <EmptyState text="Run KYC/KYB Verification after startup completion to score the held-out test packages." />
        )}
      </Panel>

      <Panel title="Run History">
        <RunHistory runs={runs.data?.items ?? []} />
      </Panel>
    </section>
  );
}

function EmailAutomationPage() {
  const slug = "email-automation";
  const queryClient = useQueryClient();
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [draftForm, setDraftForm] = useState<EmailDraftRequest>({
    customer_id: "",
    communication_type: "service",
    event_type: null,
    campaign_id: null,
    custom_context: ""
  });

  const raw = useQuery({ queryKey: ["raw", slug], queryFn: () => fetchRawData(slug) });
  const training = useStartupTraining(slug);
  const startupReady = training.data?.status === "completed";
  const startupActive = isStartupTrainingActive(training.data?.status);
  const aiHealth = useQuery({ queryKey: ["ai-health"], queryFn: fetchAiHealth });
  const runs = useQuery({ queryKey: ["runs", slug], queryFn: () => fetchRuns(slug) });
  const runInProgress = runs.data?.items.some((run) => run.status === "running") ?? false;
  const latest = useQuery({
    queryKey: ["email-automation-latest"],
    queryFn: fetchEmailAutomationLatest,
    refetchInterval: () => (runInProgress || runProgress !== null ? 1000 : false)
  });

  const runMutation = useMutation({
    mutationFn: () =>
      runUseCaseWithProgress(
        slug,
        (progress) => {
          setRunProgress(progress);
        },
        "Email Automation evaluation failed."
      ),
    onSuccess: (response) => {
      setRunProgress(null);
      const payload = isEmailAutomationPayload(response.result.payload) ? response.result.payload : null;
      if (payload?.drafts[0]?.draft_id) {
        setSelectedDraftId(payload.drafts[0].draft_id);
      }
      queryClient.invalidateQueries({ queryKey: ["email-automation-latest"] });
      queryClient.invalidateQueries({ queryKey: ["runs", slug] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    },
    onError: () => setRunProgress(null)
  });

  const draftMutation = useMutation({
    mutationFn: () => submitEmailDraft({
      ...draftForm,
      event_type: draftForm.communication_type === "service" ? draftForm.event_type || null : null,
      campaign_id: draftForm.communication_type === "campaign" ? draftForm.campaign_id || null : null,
      custom_context: draftForm.custom_context ?? ""
    }),
    onSuccess: (response) => {
      const draft = response.payload.drafts[0];
      if (draft?.draft_id) {
        setSelectedDraftId(draft.draft_id);
      }
      queryClient.invalidateQueries({ queryKey: ["email-automation-latest"] });
      queryClient.invalidateQueries({ queryKey: ["runs", slug] });
      queryClient.invalidateQueries({ queryKey: ["use-cases"] });
    }
  });

  const rawDataset = raw.data?.datasets.find((dataset) => dataset.dataset_key === "email_generation_inputs");
  const customerRecords = rawDataset?.payload.customers ?? [];
  const eventRecords = rawDataset?.payload.events ?? [];
  const campaignRecords = rawDataset?.payload.campaigns ?? [];
  const templateRecords = rawDataset?.payload.templates ?? [];
  const artifacts = raw.data?.artifacts ?? [];
  const artifactGroups = groupEmailArtifacts(artifacts);
  const mutationPayload = isEmailAutomationPayload(runMutation.data?.result.payload)
    ? runMutation.data.result.payload
    : null;
  const evaluationPayload = startupReady ? mutationPayload ?? latest.data?.latest?.payload ?? null : null;
  const draftPayload = startupReady ? draftMutation.data?.payload ?? latest.data?.latest_draft?.payload ?? null : null;
  const visibleDrafts = draftPayload?.drafts.length ? draftPayload.drafts : evaluationPayload?.drafts ?? [];
  const visibleFindings = draftPayload?.drafts.length ? draftPayload.compliance_findings : evaluationPayload?.compliance_findings ?? [];
  const visibleScores = draftPayload?.drafts.length ? draftPayload.scores : evaluationPayload?.scores ?? [];
  const selectedDraft =
    visibleDrafts.find((draft) => draft.draft_id === selectedDraftId) ?? visibleDrafts[0] ?? null;
  const selectedFindings = selectedDraft
    ? visibleFindings.filter((finding) => finding.draft_id === selectedDraft.draft_id)
    : [];
  const selectedScore = selectedDraft
    ? visibleScores.find((score) => score.draft_id === selectedDraft.draft_id) ?? null
    : null;
  const localLlm = aiHealth.data?.adapters.find((adapter) => adapter.name === "Ollama Qwen");
  const gptFallback = aiHealth.data?.adapters.find((adapter) => adapter.name === "OpenAI GPT-4o");
  const latestProvider = startupReady
    ? draftPayload?.summary.provider_used ?? evaluationPayload?.summary.provider_used ?? latest.data?.latest?.run.provider_used
    : undefined;
  const eventTypes = Array.from(new Set(eventRecords.map((event) => String(event.event_type ?? "")).filter(Boolean))).sort();
  const selectedCustomerCampaigns = campaignRecords.filter(
    (campaign) => String(campaign.customer_id ?? "") === draftForm.customer_id
  );

  useEffect(() => {
    if (!draftForm.customer_id && customerRecords[0]?.customer_id) {
      setDraftForm((current) => ({ ...current, customer_id: String(customerRecords[0].customer_id) }));
    }
  }, [customerRecords, draftForm.customer_id]);

  useEffect(() => {
    if (draftForm.communication_type !== "campaign") {
      return;
    }
    if (selectedCustomerCampaigns.some((campaign) => String(campaign.campaign_id ?? "") === draftForm.campaign_id)) {
      return;
    }
    const firstCampaignId = selectedCustomerCampaigns[0]?.campaign_id;
    if (firstCampaignId) {
      setDraftForm((current) => ({ ...current, campaign_id: String(firstCampaignId) }));
    }
  }, [draftForm.campaign_id, draftForm.communication_type, selectedCustomerCampaigns]);

  useEffect(() => {
    if (selectedDraftId && visibleDrafts.some((draft) => draft.draft_id === selectedDraftId)) {
      return;
    }
    if (visibleDrafts[0]?.draft_id) {
      setSelectedDraftId(visibleDrafts[0].draft_id);
    }
  }, [selectedDraftId, visibleDrafts]);

  return (
    <section className="space-y-6 p-8">
      <PageTitle
        icon={<Mail size={22} />}
        title="Email Automation"
        subtitle="Synthetic service and campaign draft generation with deterministic compliance rules, Ollama Qwen first, and GPT-4o fallback."
      />

      <div className="grid grid-cols-5 gap-4">
        <MetricCard label="Customers" value={rawDataset?.payload.customer_count ?? 0} />
        <MetricCard label="Service Events" value={rawDataset?.payload.service_event_count ?? 0} />
        <MetricCard label="Campaign Rows" value={rawDataset?.payload.campaign_audience_count ?? 0} />
        <MetricCard label="Templates" value={rawDataset?.payload.template_count ?? templateRecords.length} />
        <MetricCard label="Startup Status" value={training.data?.status ?? "loading"} />
      </div>

      <EmailAutomationOverviewPanel />

      <div className="grid grid-cols-[1.15fr_0.85fr] gap-5">
        <Panel title="Raw Email Inputs">
          <div className="space-y-4">
            <DataTable rows={rawDataset?.payload.preview ?? []} limit={12} />
            <div className="grid grid-cols-2 gap-3">
              {artifactGroups.map(([group, groupArtifacts]) => (
                <div key={group} className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{formatDocumentType(group)}</p>
                    <span className="text-xs text-zinc-400">{groupArtifacts.length} files</span>
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-zinc-400">
                    {groupArtifacts.map((artifact) => (
                      <div key={artifact.id} className="flex items-center gap-2">
                        <FileStack size={14} className="text-emerald-300" />
                        <span className="truncate">{artifact.file_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            {raw.isError ? <ErrorBox message={(raw.error as Error).message} /> : null}
          </div>
        </Panel>

        <Panel title="Adapter Health">
          <div className="space-y-3">
            <div className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Template Engine</p>
                  <p className="text-xs text-zinc-500">Deterministic baseline</p>
                </div>
                <CheckCircle2 className="text-emerald-500" size={18} />
              </div>
              <p className="mt-2 text-sm text-zinc-400">
                Local templates and compliance rules are always available for this synthetic MVP.
              </p>
            </div>
            <AdapterHealthRow adapter={localLlm} fallbackName="Ollama Qwen" />
            <AdapterHealthRow adapter={gptFallback} fallbackName="OpenAI GPT-4o" />
            {aiHealth.isError ? <ErrorBox message={(aiHealth.error as Error).message} /> : null}
          </div>
        </Panel>
      </div>

      <Panel title="Run Email Automation">
        <div className="space-y-4">
          <p className="text-sm text-zinc-300">
            Startup runs the deterministic email evaluation set. The run button reruns that set and persists draft,
            compliance, provider, and scoring details.
          </p>
          <button
            type="button"
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || !rawDataset || !startupReady}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
          >
            <Play size={16} />
            {runMutation.isPending ? "Running" : "Run Email Automation"}
          </button>
          {(runMutation.isPending || runProgress) && (
            <ProgressBar percent={runProgress?.progress_percent ?? 0} stage={runProgress?.stage ?? "starting"} />
          )}
          {startupActive ? (
            <ProgressBar percent={training.data?.progress_percent ?? 0} stage={`Startup: ${training.data?.stage ?? "queued"}`} />
          ) : null}
          {training.data?.status === "failed" ? (
            <ErrorBox message={training.data.error ?? "Email Automation startup evaluation failed."} />
          ) : null}
          {runMutation.isError ? <ErrorBox message={(runMutation.error as Error).message} /> : null}
          {evaluationPayload ? (
            <div className="grid grid-cols-6 gap-3">
              <MetricCard label="Provider" value={formatProviderLabel(latestProvider ?? evaluationPayload.summary.provider_used)} />
              <MetricCard label="Drafts" value={evaluationPayload.summary.draft_count} />
              <MetricCard label="Approval Rate" value={formatPercent(evaluationPayload.summary.approval_rate)} />
              <MetricCard label="Quality" value={formatPercent(evaluationPayload.summary.average_quality_score)} />
              <MetricCard label="Review Needed" value={evaluationPayload.summary.needs_review_count} />
              <MetricCard label="Fallbacks" value={evaluationPayload.summary.fallback_count} />
            </div>
          ) : (
            <EmptyState text="Startup evaluation drafts will appear when Email Automation stage 8 completes." />
          )}
        </div>
      </Panel>

      <div className="grid grid-cols-[0.9fr_1.1fr] gap-5">
        <Panel title="Draft Workspace">
          <div className="space-y-4">
            <label className="block text-sm font-medium text-zinc-300" htmlFor="email-customer">
              Customer
            </label>
            <select
              id="email-customer"
              value={draftForm.customer_id}
              onChange={(event) => setDraftForm((current) => ({ ...current, customer_id: event.target.value, campaign_id: null }))}
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none ring-emerald-500/40 focus:ring-2"
            >
              {customerRecords.slice(0, 60).map((customer) => (
                <option key={String(customer.customer_id)} value={String(customer.customer_id)}>
                  {String(customer.customer_id)} - {String(customer.first_name ?? "Synthetic customer")}
                </option>
              ))}
            </select>

            <label className="block text-sm font-medium text-zinc-300" htmlFor="email-type">
              Draft type
            </label>
            <select
              id="email-type"
              value={draftForm.communication_type}
              onChange={(event) =>
                setDraftForm((current) => ({
                  ...current,
                  communication_type: event.target.value as "service" | "campaign",
                  event_type: event.target.value === "service" ? current.event_type : null,
                  campaign_id: event.target.value === "campaign" ? current.campaign_id : null
                }))
              }
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none ring-emerald-500/40 focus:ring-2"
            >
              <option value="service">Service message</option>
              <option value="campaign">Campaign draft</option>
            </select>

            {draftForm.communication_type === "service" ? (
              <>
                <label className="block text-sm font-medium text-zinc-300" htmlFor="email-event-type">
                  Event type
                </label>
                <select
                  id="email-event-type"
                  value={draftForm.event_type ?? ""}
                  onChange={(event) => setDraftForm((current) => ({ ...current, event_type: event.target.value || null }))}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none ring-emerald-500/40 focus:ring-2"
                >
                  <option value="">Any matching service event</option>
                  {eventTypes.map((eventType) => (
                    <option key={eventType} value={eventType}>
                      {formatDocumentType(eventType)}
                    </option>
                  ))}
                </select>
              </>
            ) : (
              <>
                <label className="block text-sm font-medium text-zinc-300" htmlFor="email-campaign">
                  Campaign
                </label>
                <select
                  id="email-campaign"
                  value={draftForm.campaign_id ?? ""}
                  onChange={(event) => setDraftForm((current) => ({ ...current, campaign_id: event.target.value || null }))}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none ring-emerald-500/40 focus:ring-2"
                >
                  <option value="">Select campaign</option>
                  {selectedCustomerCampaigns.map((campaign) => (
                    <option key={String(campaign.audience_id)} value={String(campaign.campaign_id)}>
                      {String(campaign.campaign_id)} - {String(campaign.campaign_name ?? "Campaign")}
                    </option>
                  ))}
                </select>
              </>
            )}

            <label className="block text-sm font-medium text-zinc-300" htmlFor="email-context">
              Custom context
            </label>
            <textarea
              id="email-context"
              value={draftForm.custom_context ?? ""}
              onChange={(event) => setDraftForm((current) => ({ ...current, custom_context: event.target.value }))}
              rows={4}
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 p-3 text-sm text-zinc-100 outline-none ring-emerald-500/40 focus:ring-2"
            />

            <button
              type="button"
              onClick={() => draftMutation.mutate()}
              disabled={draftMutation.isPending || !rawDataset || !startupReady || !draftForm.customer_id}
              className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-emerald-950/40 hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-700"
            >
              <Send size={16} />
              {draftMutation.isPending ? "Drafting" : "Generate Draft"}
            </button>
            {draftMutation.isError ? <ErrorBox message={(draftMutation.error as Error).message} /> : null}
          </div>
        </Panel>

        <Panel title="Selected Draft Detail">
          {selectedDraft ? (
            <EmailDraftDetail draft={selectedDraft} findings={selectedFindings} score={selectedScore} />
          ) : (
            <EmptyState text="Generate a draft or wait for startup evaluation to inspect email content." />
          )}
        </Panel>
      </div>

      <Panel title="Evaluation Draft Queue">
        {evaluationPayload?.drafts.length ? (
          <EmailDraftQueue drafts={evaluationPayload.drafts} selectedDraftId={selectedDraft?.draft_id ?? null} onSelect={setSelectedDraftId} />
        ) : (
          <EmptyState text="Evaluation drafts appear after Email Automation startup completion." />
        )}
      </Panel>

      <Panel title="Run History">
        <RunHistory runs={runs.data?.items ?? []} />
      </Panel>
    </section>
  );
}

function PageTitle({ icon, title, subtitle }: { icon: ReactNode; title: string; subtitle: string }) {
  return (
    <header className="flex items-center gap-4">
      <div className="grid h-11 w-11 place-items-center rounded-md bg-zinc-900 text-emerald-300 shadow-sm ring-1 ring-zinc-800">{icon}</div>
      <div>
        <h1 className="text-2xl font-semibold tracking-normal">{title}</h1>
        <p className="text-sm text-zinc-400">{subtitle}</p>
      </div>
    </header>
  );
}

function MetricCard({
  label,
  value,
  quality
}: {
  label: string;
  value: number | string;
  quality?: "good" | "average" | "bad" | null;
}) {
  const valueSize = typeof value === "string" && value.length > 16 ? "text-xl" : "text-2xl";
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900 p-4">
      <p className="text-xs font-medium uppercase text-zinc-400">{label}</p>
      <p className={`mt-2 break-words ${valueSize} font-semibold ${quality ? qualityTextClass(quality) : ""}`}>
        {value}
      </p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-md border border-zinc-800 bg-zinc-900 p-5 shadow-sm shadow-black/20">
      <h2 className="mb-4 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function DataTable({ rows, limit }: { rows: Record<string, unknown>[]; limit?: number }) {
  const visibleRows = rows.slice(0, limit ?? rows.length);
  const columns = Object.keys(visibleRows[0] ?? {});
  if (!visibleRows.length) {
    return <EmptyState text="No raw data is available. Run database seed first." />;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-400">
            {columns.map((column) => (
              <th key={column} className="whitespace-nowrap px-3 py-2">{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row, index) => (
            <tr key={index} className="border-b border-zinc-800/80">
              {columns.map((column) => (
                <td key={column} className="whitespace-nowrap px-3 py-2">{String(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function fraudLabel(value: number) {
  return value === 1 ? "Fraud" : "Not fraud";
}

function FraudOverviewPanel({
  trainCount,
  valCount,
  testCount
}: {
  trainCount: number;
  valCount: number;
  testCount: number;
}) {
  return (
    <Panel title="Use Case Overview">
      <div className="space-y-5 text-sm leading-relaxed text-zinc-300">
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Purpose</h3>
          <p>
            Fraud Detection scores synthetic card and transfer transactions in near real time. The goal is to
            flag likely fraudulent payments before settlement, prioritize investigator review, and reduce false
            declines for legitimate customers.             All data in this MVP is generated inside the repository for safe local testing.
            Labels use probabilistic scoring with overlapping fraud and legitimate behaviour,
            customer spending profiles, and intentional label noise (~1%) so models do not see
            perfectly separable patterns.
          </p>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Data types and content</h3>
          <p className="mb-2">
            Raw artifacts are stored as XLSX under <code className="text-emerald-300">data/fraud_detection/raw/</code>.
            Each row has <strong className="text-zinc-100">27 raw fields</strong> plus ~80 engineered signals (prior
            decomposition, behavioral composites, interactions) and the supervised
            label <code className="text-emerald-300">label_is_fraud</code>.
          </p>
          <ul className="list-inside list-disc space-y-1 text-zinc-400">
            <li>Identity and account: customer_id, account_age_days, account_balance_before</li>
            <li>Payment: amount, currency, channel, transaction_type, card_type, merchant_id, merchant_category</li>
            <li>Risk signals: device_trust_score, ip_risk_score, merchant_risk_score, velocity_24h_count, failed_login_count_24h</li>
            <li>Behavioural context: hour_of_day, is_new_payee, distance_from_home_km, days_since_last_transaction, auth_method</li>
            <li>Current split: {trainCount} train / {valCount} validation / {testCount} held-out test ({trainCount + valCount + testCount} total rows)</li>
          </ul>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">How fraud detection runs</h3>
          <ol className="list-inside list-decimal space-y-2 text-zinc-400">
            <li>
              <strong className="text-zinc-200">Startup training:</strong> When you run{" "}
              <code className="text-emerald-300">npm run dev:full</code>, the backend trains an AutoGluon Tabular
              binary classifier on the train split with the{" "}
              <code className="text-emerald-300">good_quality</code> preset (LightGBM, CatBoost, RF,
              Extra Trees, and linear models; XGBoost and heavy neural learners are excluded locally) on rich engineered features. Validation is kept outside
              model fitting and used for threshold calibration plus metrics. Test is never used in fit.
            </li>
            <li>
              <strong className="text-zinc-200">Model family:</strong> AutoGluon trains a compact local portfolio, with bagging
              and stacking disabled by default for faster startup on this workstation. The leaderboard picks the best model automatically.
            </li>
            <li>
              <strong className="text-zinc-200">Run Fraud Model:</strong> Loads the trained model and scores only the test
              split. Outputs fraud probability, risk level (Low / Medium / High), operational decision, and actual vs
              predicted fraud for each test transaction.
            </li>
            <li>
              <strong className="text-zinc-200">Decision threshold:</strong> Calibrated on the validation split (max F1)
              after training; used for predicted fraud and step-up / block rules.
            </li>
          </ol>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Evaluation metrics</h3>
          <p className="mb-2">
            <strong className="text-zinc-200">Primary score: PR-AUC</strong> (average precision on the fraud class).
            It is threshold-independent and suited to imbalanced fraud data—unlike accuracy, which is dominated by
            legitimate transactions, and unlike ROC-AUC alone, which can look strong when negatives are easy to rank.
          </p>
          <ul className="list-inside list-disc space-y-1 text-zinc-400">
            <li>AutoGluon model selection uses <code className="text-emerald-300">average_precision</code> during training.</li>
            <li>
              At the calibrated threshold: <strong className="text-zinc-300">precision</strong> (fewer false blocks),{" "}
              <strong className="text-zinc-300">recall</strong> (more fraud caught), and <strong className="text-zinc-300">F1</strong>{" "}
              summarize operational trade-offs.
            </li>
            <li>Accuracy and ROC-AUC remain visible as secondary reference metrics.</li>
          </ul>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Persistence and audit</h3>
          <p>
            Training runs, validation results, test evaluations, model artifacts, and audit events are stored in
            PostgreSQL so the portal can show run history, charts, and reproducible metrics across sessions.
          </p>
        </section>
      </div>
    </Panel>
  );
}

function CreditRiskOverviewPanel({
  trainCount,
  valCount,
  testCount,
  trainDefaults,
  valDefaults,
  testDefaults
}: {
  trainCount: number;
  valCount: number;
  testCount: number;
  trainDefaults: number;
  valDefaults: number;
  testDefaults: number;
}) {
  return (
    <Panel title="Use Case Overview">
      <div className="space-y-5 text-sm leading-relaxed text-zinc-300">
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Purpose</h3>
          <p>
            Credit Risk estimates the 12-month probability of default for synthetic loan applications. It supports
            underwriting decisions, recommended credit limits, risk grades, and expected loss estimates without using
            real customer data.
          </p>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Data types and content</h3>
          <p className="mb-2">
            Raw artifacts are stored as XLSX under <code className="text-emerald-300">data/credit_risk/raw/</code>.
            Each application includes applicant affordability, credit history, debt exposure, collateral, channel, and
            the supervised label <code className="text-emerald-300">label_default_12m</code>.
          </p>
          <ul className="list-inside list-disc space-y-1 text-zinc-400">
            <li>Applicant profile: age, employment_status, employment_years, region, and channel</li>
            <li>Affordability: monthly_income, monthly_expenses, existing_debt, requested_loan_amount, requested_term_months</li>
            <li>Credit behaviour: credit_history_months, prior_defaults, delinquencies_12m, credit_utilization, recent_credit_inquiries</li>
            <li>Recovery context: home_ownership, collateral_value, target_loss_given_default</li>
            <li>
              Current split: {trainCount} train ({trainDefaults} defaults) / {valCount} validation ({valDefaults} defaults) /
              {testCount} held-out test ({testDefaults} defaults)
            </li>
          </ul>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">How credit risk runs</h3>
          <ol className="list-inside list-decimal space-y-2 text-zinc-400">
            <li>
              <strong className="text-zinc-200">Startup training:</strong> When the backend starts, AutoGluon trains a
              tabular binary classifier on the train split. Validation is used only for threshold calibration and
              startup metrics. The held-out test split is not passed to model fitting.
            </li>
            <li>
              <strong className="text-zinc-200">Feature design:</strong> The backend derives debt-to-income,
              payment-to-income, liquid reserve, collateral coverage, utilization pressure, and stability features
              before fitting the model.
            </li>
            <li>
              <strong className="text-zinc-200">Run Credit Risk Model:</strong> Loads the trained model and scores only
              the test split. Outputs PD probability, predicted default, risk grade, underwriting decision, recommended
              limit, expected loss, and top risk factors.
            </li>
            <li>
              <strong className="text-zinc-200">Decision threshold:</strong> Calibrated on the validation split with an
              F1-oriented threshold search, then reused for held-out test scoring.
            </li>
          </ol>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Evaluation metrics</h3>
          <p className="mb-2">
            <strong className="text-zinc-200">Primary score: ROC-AUC</strong>. It measures how well the model ranks
            future default cases above current accounts across thresholds. PR-AUC, precision, recall, F1, accuracy, and
            the confusion matrix remain visible for operational review.
          </p>
          <ul className="list-inside list-disc space-y-1 text-zinc-400">
            <li>AutoGluon model selection uses <code className="text-emerald-300">roc_auc</code> during training.</li>
            <li>Risk grades A-E are derived from PD probability bands, not from raw score labels.</li>
            <li>Expected loss combines PD probability, requested amount, and synthetic loss-given-default.</li>
          </ul>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Persistence and audit</h3>
          <p>
            Training runs, validation results, test evaluations, model artifacts, and audit events are stored in
            PostgreSQL, matching the same staged persistence pattern used by Fraud Detection.
          </p>
        </section>
      </div>
    </Panel>
  );
}

function DocumentOcrOverviewPanel({
  customerCount,
  documentCount
}: {
  customerCount: number;
  documentCount: number;
}) {
  return (
    <Panel title="Use Case Overview">
      <div className="space-y-5 text-sm leading-relaxed text-zinc-300">
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Purpose</h3>
          <p>
            Document OCR extracts structured banking fields and tables from synthetic customer document packages. The
            local path handles digital PDFs first, while scanned statements and notice images can use GPT-4o fallback
            because the MVP data is generated inside this project.
          </p>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Data types and content</h3>
          <p className="mb-2">
            Raw artifacts are stored under <code className="text-emerald-300">data/document_ocr/raw/</code>. Each
            customer package includes a bank statement, account confirmation, income proof, scanned statement PDF, and
            scanned-style transfer notice JPG.
          </p>
          <ul className="list-inside list-disc space-y-1 text-zinc-400">
            <li>Current package: {customerCount} synthetic customers and {documentCount} documents</li>
            <li>Digital PDFs include extractable English text and transaction tables</li>
            <li>Scanned PDFs and JPG notices route to fallback when local text coverage is low</li>
            <li>Ground truth JSON stores expected fields, table rows, and checksums for repeatable tests</li>
          </ul>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">How extraction runs</h3>
          <ol className="list-inside list-decimal space-y-2 text-zinc-400">
            <li>
              <strong className="text-zinc-200">Local PDF pass:</strong> pdfplumber extracts text and transaction rows
              from readable PDFs, with PyMuPDF used as a second local parser when needed.
            </li>
            <li>
              <strong className="text-zinc-200">Fallback pass:</strong> image-only PDFs and JPGs are rendered or read
              as images and sent to GPT-4o for strict JSON extraction when the API key is configured.
            </li>
            <li>
              <strong className="text-zinc-200">Validation:</strong> extracted fields and tables are compared against
              synthetic ground truth, then provider, confidence, warnings, and metrics are persisted in PostgreSQL.
            </li>
          </ol>
        </section>
      </div>
    </Panel>
  );
}

type AdapterHealthStatus = {
  name: string;
  available: boolean;
  provider: string;
  model_name: string | null;
  message: string;
  setup_hint?: string | null;
};

function AdapterHealthRow({
  adapter,
  fallbackName
}: {
  adapter?: AdapterHealthStatus;
  fallbackName: string;
}) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950 p-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">{adapter?.name ?? fallbackName}</p>
          <p className="text-xs text-zinc-500">{adapter?.model_name ?? "Not reported"}</p>
        </div>
        {adapter?.available ? (
          <CheckCircle2 className="text-emerald-500" size={18} />
        ) : (
          <AlertTriangle className="text-amber-500" size={18} />
        )}
      </div>
      <p className="mt-2 text-sm text-zinc-400">{adapter?.message ?? "Adapter health has not loaded yet."}</p>
      {adapter?.setup_hint ? <p className="mt-1 text-xs text-amber-200">{adapter.setup_hint}</p> : null}
    </div>
  );
}

function DocumentResultsTable({
  documents,
  selectedDocumentId,
  onSelect
}: {
  documents: DocumentExtraction[];
  selectedDocumentId: string | null;
  onSelect: (documentId: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-max text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-400">
            <th className="whitespace-nowrap px-3 py-2">Document Type</th>
            <th className="whitespace-nowrap px-3 py-2">Customer ID</th>
            <th className="whitespace-nowrap px-3 py-2">Status</th>
            <th className="whitespace-nowrap px-3 py-2">Confidence</th>
            <th className="whitespace-nowrap px-3 py-2">Provider</th>
            <th className="whitespace-nowrap px-3 py-2">Fields</th>
            <th className="whitespace-nowrap px-3 py-2">Issues</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => {
            const selected = selectedDocumentId === document.document_id;
            return (
              <tr
                key={document.document_id}
                onClick={() => onSelect(document.document_id)}
                className={[
                  "cursor-pointer border-b border-zinc-800/80 transition",
                  selected ? "bg-emerald-500/10 text-emerald-100" : "hover:bg-zinc-950"
                ].join(" ")}
              >
                <td className="whitespace-nowrap px-3 py-2 font-medium">{formatDocumentType(document.document_type)}</td>
                <td className="whitespace-nowrap px-3 py-2">{document.customer_id}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatDocumentType(document.extraction_status)}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatPercent(document.confidence)}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatProviderLabel(document.provider_used)}</td>
                <td className="whitespace-nowrap px-3 py-2">{Object.keys(document.fields).length}</td>
                <td className="whitespace-nowrap px-3 py-2">{document.validation_issues.length}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DocumentDetail({ document }: { document: DocumentExtraction }) {
  const fields = Object.entries(document.fields);
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-zinc-100">{document.document_id}</p>
        <p className="text-xs text-zinc-400">
          {formatDocumentType(document.document_type)} - {formatProviderLabel(document.provider_used, true)}
        </p>
      </div>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Extracted Fields</h3>
        {fields.length ? (
          <div className="grid gap-2">
            {fields.map(([key, value]) => (
              <div key={key} className="grid grid-cols-[0.85fr_1.15fr] gap-3 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm">
                <span className="text-zinc-400">{formatColumnHeader(key)}</span>
                <span className="break-words text-zinc-100">{formatDetailValue(value)}</span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState text="No fields were extracted for this document." />
        )}
      </section>

      {document.tables.length ? (
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-zinc-200">Extracted Tables</h3>
          {document.tables.map((table) => (
            <div key={table.name}>
              <p className="mb-2 text-xs uppercase text-zinc-500">{formatDocumentType(table.name)}</p>
              <DataTable rows={table.rows} limit={8} />
            </div>
          ))}
        </section>
      ) : null}

      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Raw Text Excerpt</h3>
        <p className="rounded-md border border-zinc-800 bg-zinc-950 p-3 text-sm text-zinc-400">
          {document.raw_text_excerpt || "No raw text excerpt is available."}
        </p>
      </section>

      {document.validation_issues.length ? (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-zinc-200">Warnings</h3>
          <ul className="space-y-2 text-sm text-amber-100">
            {document.validation_issues.map((issue) => (
              <li key={issue} className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2">
                {issue}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function SupportChatbotOverviewPanel() {
  return (
    <Panel title="Use Case Overview">
      <div className="space-y-5 text-sm leading-relaxed text-zinc-300">
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Purpose</h3>
          <p>
            Support Chatbot helps branch and contact-center staff answer synthetic banking support questions from
            generated policy, procedure, FAQ, and product notice documents. It is built for cited operational guidance,
            not open-ended customer advice.
          </p>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">How RAG Works</h3>
          <ol className="list-inside list-decimal space-y-2 text-zinc-400">
            <li>Policy PDFs, Markdown procedures, JSON FAQ entries, and notices are chunked into deterministic support sources.</li>
            <li>BM25 retrieves the top matching chunks locally for the agent question.</li>
            <li>Ollama Qwen generates strict JSON first; GPT-4o is used as fallback when local generation is unavailable or invalid.</li>
            <li>Answers, citations, provider choice, confidence, warnings, and audit events are persisted in PostgreSQL.</li>
          </ol>
        </section>
      </div>
    </Panel>
  );
}

function SupportAnswerCard({
  answer,
  onSelectSource
}: {
  answer: SupportChatbotAnswer;
  onSelectSource: (chunkId: string) => void;
}) {
  return (
    <div className="space-y-4 rounded-md border border-zinc-800 bg-zinc-950 p-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-emerald-500/15 px-2 py-1 text-emerald-200">
          {formatProviderLabel(answer.provider_used, true)}
        </span>
        <span className="rounded-full bg-zinc-800 px-2 py-1 text-zinc-300">
          Confidence {formatPercent(answer.confidence)}
        </span>
        <span className={answer.escalation_required ? "rounded-full bg-amber-500/15 px-2 py-1 text-amber-200" : "rounded-full bg-zinc-800 px-2 py-1 text-zinc-300"}>
          {answer.escalation_required ? "Escalation required" : "No escalation flag"}
        </span>
      </div>
      <p className="text-sm leading-relaxed text-zinc-100">{answer.answer}</p>
      {answer.escalation_reason ? <ErrorBox message={answer.escalation_reason} /> : null}
      {answer.policy_tags.length ? (
        <div className="flex flex-wrap gap-2">
          {answer.policy_tags.map((tag) => (
            <span key={tag} className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-zinc-300">
              {formatDocumentType(tag)}
            </span>
          ))}
        </div>
      ) : null}
      <div>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Citations</h3>
        {answer.sources.length ? (
          <div className="space-y-2">
            {answer.sources.map((source) => (
              <button
                key={`${source.chunk_id}-${source.source_id}`}
                type="button"
                onClick={() => onSelectSource(source.chunk_id)}
                className="block w-full rounded-md border border-zinc-800 bg-zinc-900 p-3 text-left text-sm transition hover:border-emerald-500/50"
              >
                <span className="font-medium text-zinc-100">{source.title}</span>
                <span className="ml-2 text-xs text-zinc-500">{source.source_file}</span>
                <p className="mt-1 line-clamp-2 text-xs text-zinc-400">{source.quote}</p>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState text="No citations were returned." />
        )}
      </div>
      {[...answer.missing_information, ...answer.warnings].length ? (
        <div className="space-y-2">
          {[...answer.missing_information, ...answer.warnings].map((warning) => (
            <div key={warning} className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-sm text-amber-100">
              {warning}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SupportEvaluationTable({
  answers,
  onSelectSource
}: {
  answers: SupportChatbotAnswer[];
  onSelectSource: (chunkId: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-max text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-400">
            <th className="whitespace-nowrap px-3 py-2">Question</th>
            <th className="whitespace-nowrap px-3 py-2">Status</th>
            <th className="whitespace-nowrap px-3 py-2">Provider</th>
            <th className="whitespace-nowrap px-3 py-2">Confidence</th>
            <th className="whitespace-nowrap px-3 py-2">Escalation</th>
            <th className="whitespace-nowrap px-3 py-2">Sources</th>
          </tr>
        </thead>
        <tbody>
          {answers.map((answer) => (
            <tr key={answer.question_id ?? answer.question} className="border-b border-zinc-800/80">
              <td className="max-w-[420px] px-3 py-2">{answer.question}</td>
              <td className="whitespace-nowrap px-3 py-2">{formatDocumentType(answer.answer_status)}</td>
              <td className="whitespace-nowrap px-3 py-2">{formatProviderLabel(answer.provider_used)}</td>
              <td className="whitespace-nowrap px-3 py-2">{formatPercent(answer.confidence)}</td>
              <td className="whitespace-nowrap px-3 py-2">{answer.escalation_required ? "Yes" : "No"}</td>
              <td className="whitespace-nowrap px-3 py-2">
                <div className="flex gap-2">
                  {answer.sources.slice(0, 3).map((source) => (
                    <button
                      key={source.chunk_id}
                      type="button"
                      onClick={() => onSelectSource(source.chunk_id)}
                      className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-emerald-200 hover:bg-emerald-500/15"
                    >
                      {source.source_id.replace("SUPPORT-", "")}
                    </button>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SupportSourceDetail({ chunk }: { chunk: SupportKnowledgeChunk }) {
  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-medium text-zinc-100">{chunk.title}</p>
        <p className="text-xs text-zinc-400">
          {chunk.source_id} - {chunk.source_file} - {formatDocumentType(chunk.topic)}
        </p>
      </div>
      <p className="rounded-md border border-zinc-800 bg-zinc-950 p-3 text-sm leading-relaxed text-zinc-300">
        {chunk.text}
      </p>
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Source Type" value={formatDocumentType(chunk.source_type)} />
        <MetricCard label="Start" value={chunk.char_start} />
        <MetricCard label="End" value={chunk.char_end} />
      </div>
    </div>
  );
}

function LiquidityOverviewPanel() {
  return (
    <Panel title="Use Case Overview">
      <div className="space-y-5 text-sm leading-relaxed text-zinc-300">
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Purpose</h3>
          <p>
            Liquidity Forecast estimates synthetic cash demand for branch vaults and ATMs, then converts the forecast
            into stockout risk and replenishment guidance for treasury operations.
          </p>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Forecast Design</h3>
          <ol className="list-inside list-decimal space-y-2 text-zinc-400">
            <li>Raw Excel history, holdout actuals, holiday calendars, campaign calendars, and a cash policy PDF are generated together.</li>
            <li>AutoGluon TimeSeries is attempted when available in the local Python environment.</li>
            <li>A deterministic local seasonal baseline runs when AutoGluon TimeSeries is unavailable or skipped.</li>
            <li>Metrics compare the forecast horizon against synthetic ground truth and store quantiles, errors, stockout risk, and audit events.</li>
          </ol>
        </section>
      </div>
    </Panel>
  );
}

function SeriesSelector({
  profiles,
  selectedSeriesId,
  onSelect
}: {
  profiles: LiquidityLocationProfile[];
  selectedSeriesId: string;
  onSelect: (seriesId: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {profiles.map((profile) => (
        <button
          key={profile.series_id}
          type="button"
          onClick={() => onSelect(profile.series_id)}
          className={[
            "rounded-md border px-3 py-2 text-left text-xs transition",
            selectedSeriesId === profile.series_id
              ? "border-emerald-500 bg-emerald-500/15 text-emerald-100"
              : "border-zinc-800 bg-zinc-950 text-zinc-300 hover:border-zinc-600"
          ].join(" ")}
        >
          <span className="block font-medium">{profile.location_name}</span>
          <span className="text-zinc-500">{formatDocumentType(profile.location_type)} - {profile.region}</span>
        </button>
      ))}
    </div>
  );
}

function LiquidityForecastChart({ forecasts }: { forecasts: LiquidityForecastRecord[] }) {
  const chartRows = forecasts.map((forecast) => ({
    date: forecast.date,
    actual: forecast.actual_net_cash_demand ?? null,
    p50: forecast.predicted_p50,
    p90: forecast.predicted_p90,
    replenishment: forecast.recommended_replenishment
  }));
  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={chartRows}>
        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
        <XAxis dataKey="date" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
        <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} tickFormatter={(value) => `$${Math.round(Number(value) / 1000)}k`} />
        <Tooltip formatter={(value) => formatMoney(Number(value))} contentStyle={{ background: "#09090b", border: "1px solid #27272a" }} />
        <Legend />
        <Line type="monotone" dataKey="actual" stroke="#fbbf24" strokeWidth={2} name="Actual demand" />
        <Line type="monotone" dataKey="p50" stroke="#34d399" strokeWidth={2} name="P50 forecast" />
        <Line type="monotone" dataKey="p90" stroke="#60a5fa" strokeWidth={2} name="P90 forecast" />
        <Line type="monotone" dataKey="replenishment" stroke="#f472b6" strokeWidth={2} name="Replenishment" />
      </LineChart>
    </ResponsiveContainer>
  );
}

function LiquiditySeriesDetail({
  profile,
  forecasts
}: {
  profile: LiquidityLocationProfile;
  forecasts: LiquidityForecastRecord[];
}) {
  const highRisk = forecasts.filter((forecast) => forecast.stockout_risk >= 0.55);
  const totalRecommendation = forecasts.reduce((sum, forecast) => sum + forecast.recommended_replenishment, 0);
  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-medium text-zinc-100">{profile.location_name}</p>
        <p className="text-xs text-zinc-400">
          {profile.series_id} - {formatDocumentType(profile.location_type)} - {profile.region}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Recent Average" value={formatMoney(profile.recent_average_demand)} />
        <MetricCard label="Recent Peak" value={formatMoney(profile.recent_peak_demand)} />
        <MetricCard label="Last Cash" value={formatMoney(profile.last_closing_cash)} />
        <MetricCard label="Minimum Buffer" value={formatMoney(profile.minimum_cash_threshold)} />
        <MetricCard label="High Risk Days" value={highRisk.length} />
        <MetricCard label="Recommended Cash" value={formatMoney(totalRecommendation)} />
      </div>
      {highRisk.length ? (
        <div className="space-y-2">
          {highRisk.slice(0, 4).map((forecast) => (
            <div key={forecast.forecast_id} className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-sm text-amber-100">
              {forecast.date}: risk {formatPercent(forecast.stockout_risk)}, recommend {formatMoney(forecast.recommended_replenishment)}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState text="No high-risk forecast days for the selected series." />
      )}
    </div>
  );
}

function LiquidityForecastTable({
  forecasts,
  onSelectSeries
}: {
  forecasts: LiquidityForecastRecord[];
  onSelectSeries: (seriesId: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-max text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-400">
            <th className="whitespace-nowrap px-3 py-2">Date</th>
            <th className="whitespace-nowrap px-3 py-2">Location</th>
            <th className="whitespace-nowrap px-3 py-2">Type</th>
            <th className="whitespace-nowrap px-3 py-2">Actual</th>
            <th className="whitespace-nowrap px-3 py-2">P50</th>
            <th className="whitespace-nowrap px-3 py-2">P90</th>
            <th className="whitespace-nowrap px-3 py-2">Error</th>
            <th className="whitespace-nowrap px-3 py-2">Stockout Risk</th>
            <th className="whitespace-nowrap px-3 py-2">Replenishment</th>
            <th className="whitespace-nowrap px-3 py-2">Reason</th>
          </tr>
        </thead>
        <tbody>
          {forecasts.map((forecast) => {
            const riskClass =
              forecast.stockout_risk >= 0.55
                ? "text-amber-200"
                : forecast.stockout_risk >= 0.35
                  ? "text-yellow-300"
                  : "text-emerald-300";
            return (
              <tr key={forecast.forecast_id} className="border-b border-zinc-800/80 hover:bg-zinc-950">
                <td className="whitespace-nowrap px-3 py-2">{forecast.date}</td>
                <td className="whitespace-nowrap px-3 py-2">
                  <button type="button" onClick={() => onSelectSeries(forecast.series_id)} className="text-left text-emerald-200 hover:text-emerald-100">
                    {forecast.location_name}
                  </button>
                </td>
                <td className="whitespace-nowrap px-3 py-2">{formatDocumentType(forecast.location_type)}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatMoney(forecast.actual_net_cash_demand ?? 0)}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatMoney(forecast.predicted_p50)}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatMoney(forecast.predicted_p90)}</td>
                <td className="whitespace-nowrap px-3 py-2">{forecast.absolute_error == null ? "-" : formatMoney(forecast.absolute_error)}</td>
                <td className={`whitespace-nowrap px-3 py-2 font-medium ${riskClass}`}>{formatPercent(forecast.stockout_risk)}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatMoney(forecast.recommended_replenishment)}</td>
                <td className="max-w-[360px] px-3 py-2 text-zinc-400">{forecast.reason_codes.join(", ")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AmlOverviewPanel() {
  return (
    <Panel title="Use Case Overview">
      <div className="space-y-5 text-sm leading-relaxed text-zinc-300">
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Purpose</h3>
          <p>
            AML Monitoring prioritizes synthetic alerts for analyst review. It combines tabular risk scoring,
            deterministic network signals, and narrative drafting so investigators can see probability, decision,
            top factors, linked entities, and synthetic SAR draft evidence in one workflow.
          </p>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Model Flow</h3>
          <ol className="list-inside list-decimal space-y-2 text-zinc-400">
            <li>Generated train, validation, and held-out test alert workbooks are loaded from local raw artifacts.</li>
            <li>Network and entity features enrich each alert without using external graph dependencies.</li>
            <li>AutoGluon Tabular trains at startup and validation tunes the operational SAR threshold.</li>
            <li>Ollama Qwen drafts narrative JSON first; GPT-4o is used as fallback when local generation is unavailable, times out, or returns invalid JSON.</li>
            <li>Scores, metrics, narrative drafts, model artifacts, and audit events are persisted in PostgreSQL.</li>
          </ol>
        </section>
      </div>
    </Panel>
  );
}

function AmlAlertQueue({
  alerts,
  selectedAlertId,
  onSelect
}: {
  alerts: AmlAlertDecision[];
  selectedAlertId: string | null;
  onSelect: (alertId: string) => void;
}) {
  const sortedAlerts = [...alerts].sort((left, right) => right.sar_probability - left.sar_probability).slice(0, 80);
  return (
    <div className="overflow-x-auto">
      <table className="min-w-max text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-400">
            <th className="whitespace-nowrap px-3 py-2">Alert</th>
            <th className="whitespace-nowrap px-3 py-2">Customer</th>
            <th className="whitespace-nowrap px-3 py-2">Typology</th>
            <th className="whitespace-nowrap px-3 py-2">Probability</th>
            <th className="whitespace-nowrap px-3 py-2">Risk</th>
            <th className="whitespace-nowrap px-3 py-2">Decision</th>
            <th className="whitespace-nowrap px-3 py-2">Transactions</th>
          </tr>
        </thead>
        <tbody>
          {sortedAlerts.map((alert) => {
            const selected = alert.alert_id === selectedAlertId;
            return (
              <tr
                key={alert.alert_id}
                onClick={() => onSelect(alert.alert_id)}
                className={[
                  "cursor-pointer border-b border-zinc-800/80 transition",
                  selected ? "bg-emerald-500/10 text-emerald-100" : "hover:bg-zinc-950"
                ].join(" ")}
              >
                <td className="whitespace-nowrap px-3 py-2 font-medium">{alert.alert_id}</td>
                <td className="whitespace-nowrap px-3 py-2">{alert.customer_id}</td>
                <td className="whitespace-nowrap px-3 py-2">{alert.typology_tag}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatPercent(alert.sar_probability)}</td>
                <td className={`whitespace-nowrap px-3 py-2 font-medium ${amlRiskClass(alert.risk_level)}`}>{alert.risk_level}</td>
                <td className="whitespace-nowrap px-3 py-2">{alert.decision}</td>
                <td className="whitespace-nowrap px-3 py-2">{alert.linked_transaction_count}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AmlAlertDetail({
  alert,
  narrative
}: {
  alert: AmlAlertDecision;
  narrative: AmlNarrativeDraft | null;
}) {
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-zinc-100">{alert.alert_id}</p>
        <p className="text-xs text-zinc-400">
          {alert.customer_id} - {alert.account_id} - {formatProviderLabel(alert.provider_used, true)}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="SAR Probability" value={formatPercent(alert.sar_probability)} />
        <MetricCard label="Risk Level" value={alert.risk_level} />
        <MetricCard label="Decision" value={alert.decision} />
        <MetricCard label="Related Entities" value={alert.related_entities.length} />
      </div>
      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Top Factors</h3>
        <ul className="space-y-2 text-sm text-zinc-300">
          {alert.top_factors.map((factor) => (
            <li key={factor} className="rounded-md border border-zinc-800 bg-zinc-950 p-2">
              {factor}
            </li>
          ))}
        </ul>
      </section>
      {alert.related_entities.length ? (
        <section>
          <h3 className="mb-2 text-sm font-semibold text-zinc-200">Related Entities</h3>
          <div className="flex flex-wrap gap-2">
            {alert.related_entities.map((entity) => (
              <span key={entity} className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-zinc-300">
                {entity}
              </span>
            ))}
          </div>
        </section>
      ) : null}
      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Narrative Draft</h3>
        {narrative ? (
          <div className="space-y-3 rounded-md border border-zinc-800 bg-zinc-950 p-3 text-sm">
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-emerald-500/15 px-2 py-1 text-emerald-200">
                {formatProviderLabel(narrative.provider_used, true)}
              </span>
              <span className="rounded-full bg-zinc-800 px-2 py-1 text-zinc-300">
                Confidence {formatPercent(narrative.confidence)}
              </span>
              <span className="rounded-full bg-zinc-800 px-2 py-1 text-zinc-300">
                {formatDocumentType(narrative.narrative_status)}
              </span>
            </div>
            <p className="leading-relaxed text-zinc-100">{narrative.summary}</p>
            <div>
              <p className="mb-2 font-medium text-zinc-200">Evidence</p>
              <ul className="list-inside list-disc space-y-1 text-zinc-400">
                {narrative.evidence_bullets.map((bullet) => (
                  <li key={bullet}>{bullet}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-2 font-medium text-zinc-200">Next Steps</p>
              <ul className="list-inside list-disc space-y-1 text-zinc-400">
                {narrative.recommended_next_steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ul>
            </div>
            {[...narrative.missing_information, ...narrative.warnings].length ? (
              <div className="space-y-2">
                {[...narrative.missing_information, ...narrative.warnings].map((warning) => (
                  <div key={warning} className="rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-amber-100">
                    {warning}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <EmptyState text="A narrative draft is generated for the highest-risk alerts in each run." />
        )}
      </section>
    </div>
  );
}

function AmlNetworkSummaryPanel({ payload }: { payload: AmlMonitoringPayload }) {
  const network = payload.network_summary;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Accounts" value={network.account_count} />
        <MetricCard label="Counterparties" value={network.counterparty_count} />
        <MetricCard label="Transactions" value={network.transaction_count} />
        <MetricCard label="Clusters" value={network.cluster_count} />
        <MetricCard label="Entities" value={network.entity_count} />
        <MetricCard label="High-Risk Clusters" value={network.high_risk_cluster_count} />
      </div>
      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Top Clusters</h3>
        <DataTable rows={network.top_clusters} limit={5} />
      </section>
      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Case Notes</h3>
        <p className="rounded-md border border-zinc-800 bg-zinc-950 p-3 text-sm leading-relaxed text-zinc-400">
          {payload.case_note_summary.guidance_excerpt}
        </p>
      </section>
    </div>
  );
}

function KycKybOverviewPanel() {
  return (
    <Panel title="Use Case Overview">
      <div className="grid grid-cols-4 gap-4 text-sm text-zinc-300">
        <section className="rounded-md border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="mb-2 font-semibold text-zinc-100">Onboarding Purpose</h3>
          <p>
            Verify synthetic retail KYC and business KYB packages before account opening or manual review routing.
          </p>
        </section>
        <section className="rounded-md border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="mb-2 font-semibold text-zinc-100">Data Sources</h3>
          <p>
            Generated IDs, proof documents, Excel forms, ownership files, sanctions references, and jurisdiction policies.
          </p>
        </section>
        <section className="rounded-md border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="mb-2 font-semibold text-zinc-100">Decision Flow</h3>
          <p>
            Local extraction feeds deterministic rules and AutoGluon scoring; hard rules remain authoritative for rejections.
          </p>
        </section>
        <section className="rounded-md border border-zinc-800 bg-zinc-950 p-4">
          <h3 className="mb-2 font-semibold text-zinc-100">Fallback Rules</h3>
          <p>
            Image-only artifacts use generated local hints first; GPT-4o is reserved for missing image extraction hints.
          </p>
        </section>
      </div>
    </Panel>
  );
}

function KycKybPackageQueue({
  decisions,
  selectedPackageId,
  onSelect
}: {
  decisions: KycKybPackageDecision[];
  selectedPackageId: string | null;
  onSelect: (packageId: string) => void;
}) {
  const sortedDecisions = [...decisions].sort((left, right) => right.risk_score - left.risk_score).slice(0, 80);
  return (
    <div className="overflow-x-auto">
      <table className="min-w-max text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-400">
            <th className="whitespace-nowrap px-3 py-2">Package</th>
            <th className="whitespace-nowrap px-3 py-2">Subject</th>
            <th className="whitespace-nowrap px-3 py-2">Type</th>
            <th className="whitespace-nowrap px-3 py-2">Status</th>
            <th className="whitespace-nowrap px-3 py-2">Risk Score</th>
            <th className="whitespace-nowrap px-3 py-2">Risk</th>
            <th className="whitespace-nowrap px-3 py-2">Issues</th>
          </tr>
        </thead>
        <tbody>
          {sortedDecisions.map((decision) => {
            const selected = decision.package_id === selectedPackageId;
            const issueCount = decision.missing_documents.length + decision.field_mismatches.length;
            return (
              <tr
                key={decision.package_id}
                onClick={() => onSelect(decision.package_id)}
                className={[
                  "cursor-pointer border-b border-zinc-800/80 transition",
                  selected ? "bg-emerald-500/10 text-emerald-100" : "hover:bg-zinc-950"
                ].join(" ")}
              >
                <td className="whitespace-nowrap px-3 py-2 font-medium">{decision.package_id}</td>
                <td className="whitespace-nowrap px-3 py-2">{decision.subject_name}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatDocumentType(decision.subject_type)}</td>
                <td className="whitespace-nowrap px-3 py-2">{decision.verification_status}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatPercent(decision.risk_score)}</td>
                <td className={`whitespace-nowrap px-3 py-2 font-medium ${kycRiskClass(decision.risk_level)}`}>{decision.risk_level}</td>
                <td className="whitespace-nowrap px-3 py-2">{issueCount}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function KycKybPackageDetail({
  decision,
  documents,
  findings
}: {
  decision: KycKybPackageDecision;
  documents: KycKybExtractedDocument[];
  findings: KycKybRuleFinding[];
}) {
  const failedFindings = findings.filter((finding) => finding.status === "failed");
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-zinc-100">{decision.package_id}</p>
        <p className="text-xs text-zinc-400">
          {decision.subject_name} - {formatDocumentType(decision.subject_type)} - {formatProviderLabel(decision.provider_used, true)}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Status" value={decision.verification_status} />
        <MetricCard label="Risk Score" value={formatPercent(decision.risk_score)} />
        <MetricCard label="Risk Level" value={decision.risk_level} />
        <MetricCard label="Hard Rule" value={decision.hard_rule_triggered ? "Triggered" : "Clear"} />
      </div>
      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Top Factors</h3>
        <ul className="space-y-2 text-sm text-zinc-300">
          {decision.top_factors.map((factor) => (
            <li key={factor} className="rounded-md border border-zinc-800 bg-zinc-950 p-2">
              {factor}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Documents</h3>
        <div className="space-y-2">
          {documents.map((document) => (
            <div key={document.document_id} className="rounded-md border border-zinc-800 bg-zinc-950 p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">{formatDocumentType(document.document_type)}</p>
                <span className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-zinc-300">
                  {formatProviderLabel(document.provider_used)}
                </span>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-zinc-400">
                <span>Status: {formatDocumentType(document.extraction_status)}</span>
                <span>Confidence: {formatPercent(document.confidence)}</span>
                <span>Fields: {Object.keys(document.fields).length}</span>
                <span>Issues: {document.validation_issues.length}</span>
              </div>
              {Object.keys(document.fields).length ? (
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-zinc-300">
                  {Object.entries(document.fields).slice(0, 8).map(([key, value]) => (
                    <div key={key} className="rounded-md bg-zinc-900 px-2 py-1">
                      <span className="text-zinc-500">{key}: </span>
                      <span>{formatDetailValue(value)}</span>
                    </div>
                  ))}
                </div>
              ) : null}
              {document.validation_issues.length ? (
                <div className="mt-3 space-y-1">
                  {document.validation_issues.slice(0, 4).map((issue) => (
                    <p key={issue} className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-xs text-amber-100">
                      {issue}
                    </p>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>
      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Rule Findings</h3>
        {failedFindings.length ? (
          <div className="space-y-2">
            {failedFindings.map((finding) => (
              <div key={`${finding.package_id}-${finding.rule_id}`} className="rounded-md border border-zinc-800 bg-zinc-950 p-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{formatDocumentType(finding.rule_id)}</p>
                  <span className={finding.severity === "hard_fail" ? "text-red-300" : "text-amber-200"}>
                    {formatDocumentType(finding.severity)}
                  </span>
                </div>
                <p className="mt-2 text-zinc-400">{finding.message}</p>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState text="No failed rule findings for this package." />
        )}
      </section>
    </div>
  );
}

function EmailAutomationOverviewPanel() {
  return (
    <Panel title="Use Case Overview">
      <div className="grid gap-5 text-sm leading-relaxed text-zinc-300 lg:grid-cols-3">
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Purpose</h3>
          <p>
            Email Automation drafts synthetic service notices and campaign messages, then applies deterministic policy
            checks before storing each draft and score in PostgreSQL.
          </p>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Data Sources</h3>
          <p>
            Customer profiles, service events, campaign plans, templates, compliance policy PDFs, and tone guidelines
            are generated locally under the Email Automation data folder.
          </p>
        </section>
        <section>
          <h3 className="mb-2 font-semibold text-zinc-100">Provider Flow</h3>
          <p>
            The template engine creates a baseline, Ollama Qwen drafts JSON first, GPT-4o is used as fallback, and
            compliance rules remain authoritative for final status.
          </p>
        </section>
      </div>
    </Panel>
  );
}

function EmailDraftQueue({
  drafts,
  selectedDraftId,
  onSelect
}: {
  drafts: EmailAutomationDraft[];
  selectedDraftId: string | null;
  onSelect: (draftId: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-max text-left text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-400">
            <th className="whitespace-nowrap px-3 py-2">Draft</th>
            <th className="whitespace-nowrap px-3 py-2">Customer</th>
            <th className="whitespace-nowrap px-3 py-2">Type</th>
            <th className="whitespace-nowrap px-3 py-2">Compliance</th>
            <th className="whitespace-nowrap px-3 py-2">Risk</th>
            <th className="whitespace-nowrap px-3 py-2">Provider</th>
            <th className="whitespace-nowrap px-3 py-2">Issues</th>
          </tr>
        </thead>
        <tbody>
          {drafts.map((draft) => {
            const selected = draft.draft_id === selectedDraftId;
            return (
              <tr
                key={draft.draft_id}
                onClick={() => onSelect(draft.draft_id)}
                className={[
                  "cursor-pointer border-b border-zinc-800/80 transition",
                  selected ? "bg-emerald-500/10 text-emerald-100" : "hover:bg-zinc-950"
                ].join(" ")}
              >
                <td className="whitespace-nowrap px-3 py-2 font-medium">{draft.draft_id}</td>
                <td className="whitespace-nowrap px-3 py-2">{draft.customer_id}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatDocumentType(draft.communication_type)}</td>
                <td className="whitespace-nowrap px-3 py-2">{draft.compliance_status}</td>
                <td className={`whitespace-nowrap px-3 py-2 ${emailRiskClass(draft.risk_level)}`}>{draft.risk_level}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatProviderLabel(draft.provider_used)}</td>
                <td className="whitespace-nowrap px-3 py-2">{draft.validation_issues.length}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function EmailDraftDetail({
  draft,
  findings,
  score
}: {
  draft: EmailAutomationDraft;
  findings: EmailComplianceFinding[];
  score: EmailAutomationScore | null;
}) {
  const failedFindings = findings.filter((finding) => finding.status !== "pass");
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-emerald-500/15 px-2 py-1 text-emerald-200">
          {formatProviderLabel(draft.provider_used, true)}
        </span>
        <span className="rounded-full bg-zinc-800 px-2 py-1 text-zinc-300">
          {formatDocumentType(draft.communication_type)}
        </span>
        <span className={`rounded-full bg-zinc-800 px-2 py-1 ${emailRiskClass(draft.risk_level)}`}>
          {draft.risk_level}
        </span>
      </div>

      <section className="rounded-md border border-zinc-800 bg-zinc-950 p-4">
        <p className="text-xs uppercase text-zinc-500">Subject</p>
        <p className="mt-1 text-lg font-semibold text-zinc-100">{draft.subject}</p>
        <p className="mt-3 text-xs uppercase text-zinc-500">Preheader</p>
        <p className="mt-1 text-sm text-zinc-300">{draft.preheader}</p>
        <p className="mt-3 text-xs uppercase text-zinc-500">Body</p>
        <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-zinc-300">{draft.body}</p>
        <p className="mt-3 text-xs uppercase text-zinc-500">CTA</p>
        <p className="mt-1 text-sm font-medium text-emerald-200">{draft.call_to_action}</p>
      </section>

      <div className="grid grid-cols-4 gap-3">
        <MetricCard label="Confidence" value={formatPercent(draft.confidence)} />
        <MetricCard label="Compliance" value={draft.compliance_status} />
        <MetricCard label="Quality" value={score ? formatPercent(score.quality_score) : "N/A"} />
        <MetricCard label="Personalization" value={score ? formatPercent(score.personalization_score) : "N/A"} />
      </div>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Disclosures</h3>
        {draft.required_disclosures.length ? (
          <div className="space-y-2">
            {draft.required_disclosures.map((disclosure) => (
              <p key={disclosure} className="rounded-md border border-zinc-800 bg-zinc-950 p-2 text-sm text-zinc-300">
                {disclosure}
              </p>
            ))}
          </div>
        ) : (
          <EmptyState text="No disclosures were included in this draft." />
        )}
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Compliance Findings</h3>
        {failedFindings.length ? (
          <div className="space-y-2">
            {failedFindings.map((finding) => (
              <div key={`${finding.draft_id}-${finding.rule_id}`} className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-100">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{formatDocumentType(finding.rule_id)}</p>
                  <span>{formatDocumentType(finding.severity)}</span>
                </div>
                <p className="mt-2">{finding.message}</p>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState text="No failed compliance findings for this draft." />
        )}
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-zinc-200">Personalization</h3>
        <div className="flex flex-wrap gap-2">
          {draft.personalization_used.map((item) => (
            <span key={item} className="rounded-full bg-zinc-800 px-2 py-1 text-xs text-zinc-300">
              {formatDocumentType(item)}
            </span>
          ))}
          {!draft.personalization_used.length ? <span className="text-sm text-zinc-500">No personalization fields.</span> : null}
        </div>
      </section>

      {draft.validation_issues.length || draft.warnings.length ? (
        <section className="space-y-2">
          {[...draft.validation_issues, ...draft.warnings].map((warning) => (
            <ErrorBox key={warning} message={warning} />
          ))}
        </section>
      ) : null}
    </div>
  );
}

function groupSupportArtifacts(artifacts: RawArtifact[]) {
  const grouped = new Map<string, RawArtifact[]>();
  for (const artifact of artifacts) {
    const relative = String(artifact.metadata_json?.relative_path ?? "");
    const group = relative.includes("/") ? relative.split("/")[0] : artifact.dataset_key;
    const current = grouped.get(group) ?? [];
    current.push(artifact);
    grouped.set(group, current);
  }
  return Array.from(grouped.entries()).sort(([left], [right]) => left.localeCompare(right));
}

function groupLiquidityArtifacts(artifacts: RawArtifact[]) {
  const grouped = new Map<string, RawArtifact[]>();
  for (const artifact of artifacts) {
    const relative = String(artifact.metadata_json?.relative_path ?? "");
    let group = artifact.dataset_key;
    if (relative.startsWith("raw/")) {
      group = relative.split("/")[1] ?? artifact.dataset_key;
    }
    const current = grouped.get(group) ?? [];
    current.push(artifact);
    grouped.set(group, current);
  }
  return Array.from(grouped.entries()).sort(([left], [right]) => left.localeCompare(right));
}

function groupAmlArtifacts(artifacts: RawArtifact[]) {
  const grouped = new Map<string, RawArtifact[]>();
  for (const artifact of artifacts) {
    const relative = String(artifact.metadata_json?.relative_path ?? "");
    let group = artifact.dataset_key;
    if (relative.startsWith("raw/")) {
      group = relative.split("/")[1] ?? artifact.dataset_key;
    }
    const current = grouped.get(group) ?? [];
    current.push(artifact);
    grouped.set(group, current);
  }
  return Array.from(grouped.entries()).sort(([left], [right]) => left.localeCompare(right));
}

function groupKycKybArtifacts(artifacts: RawArtifact[]) {
  const grouped = new Map<string, RawArtifact[]>();
  for (const artifact of artifacts) {
    const relative = String(artifact.metadata_json?.relative_path ?? "");
    let group = artifact.dataset_key;
    if (relative.startsWith("raw/individuals")) {
      group = "individuals";
    } else if (relative.startsWith("raw/businesses")) {
      group = "businesses";
    } else if (relative.startsWith("raw/reference")) {
      group = "reference";
    }
    const current = grouped.get(group) ?? [];
    current.push(artifact);
    grouped.set(group, current);
  }
  return Array.from(grouped.entries()).sort(([left], [right]) => left.localeCompare(right));
}

function groupEmailArtifacts(artifacts: RawArtifact[]) {
  const grouped = new Map<string, RawArtifact[]>();
  for (const artifact of artifacts) {
    const relative = String(artifact.metadata_json?.relative_path ?? "");
    let group = artifact.dataset_key;
    if (relative.startsWith("raw/")) {
      group = relative.split("/")[1] ?? artifact.dataset_key;
    }
    const current = grouped.get(group) ?? [];
    current.push(artifact);
    grouped.set(group, current);
  }
  return Array.from(grouped.entries()).sort(([left], [right]) => left.localeCompare(right));
}

function groupDocumentArtifacts(artifacts: RawArtifact[]) {
  const grouped = new Map<string, RawArtifact[]>();
  const supportFiles: RawArtifact[] = [];
  for (const artifact of artifacts) {
    if (artifact.dataset_key.startsWith("CUST-OCR")) {
      const current = grouped.get(artifact.dataset_key) ?? [];
      current.push(artifact);
      grouped.set(artifact.dataset_key, current);
    } else {
      supportFiles.push(artifact);
    }
  }
  return {
    customerGroups: Array.from(grouped.entries()).sort(([left], [right]) => left.localeCompare(right)),
    supportFiles: supportFiles.sort((left, right) => left.file_name.localeCompare(right.file_name))
  };
}

function isDocumentOcrPayload(payload: unknown): payload is DocumentOcrPayload {
  return Boolean(
    payload &&
      typeof payload === "object" &&
      "summary" in payload &&
      "documents" in payload &&
      Array.isArray((payload as DocumentOcrPayload).documents)
  );
}

function isSupportChatbotPayload(payload: unknown): payload is SupportChatbotPayload {
  return Boolean(
    payload &&
      typeof payload === "object" &&
      "summary" in payload &&
      "answers" in payload &&
      Array.isArray((payload as SupportChatbotPayload).answers)
  );
}

function isLiquidityForecastPayload(payload: unknown): payload is LiquidityForecastPayload {
  return Boolean(
    payload &&
      typeof payload === "object" &&
      "summary" in payload &&
      "forecasts" in payload &&
      Array.isArray((payload as LiquidityForecastPayload).forecasts)
  );
}

function isAmlMonitoringPayload(payload: unknown): payload is AmlMonitoringPayload {
  return Boolean(
    payload &&
      typeof payload === "object" &&
      "summary" in payload &&
      "alerts" in payload &&
      Array.isArray((payload as AmlMonitoringPayload).alerts)
  );
}

function isKycKybPayload(payload: unknown): payload is KycKybPayload {
  return Boolean(
    payload &&
      typeof payload === "object" &&
      "summary" in payload &&
      "risk_decisions" in payload &&
      Array.isArray((payload as KycKybPayload).risk_decisions)
  );
}

function isEmailAutomationPayload(payload: unknown): payload is EmailAutomationPayload {
  return Boolean(
    payload &&
      typeof payload === "object" &&
      "summary" in payload &&
      "drafts" in payload &&
      Array.isArray((payload as EmailAutomationPayload).drafts)
  );
}

function formatProviderLabel(provider?: string | null, withPrefix = false) {
  const label =
    provider === "gpt-4o-fallback"
      ? "GPT-4o fallback"
    : provider === "mixed-local-gpt4o"
        ? "Mixed local + GPT-4o fallback"
      : provider === "local-autogluon+local-ollama"
        ? "AutoGluon + Ollama Qwen"
      : provider === "local-autogluon+gpt-4o-fallback"
        ? "AutoGluon + GPT-4o fallback"
      : provider === "local-autogluon+mixed-local-gpt4o"
        ? "AutoGluon + mixed LLM"
      : provider === "local-ocr-rules-autogluon"
        ? "Local OCR + rules + AutoGluon"
      : provider === "local-ocr-rules-autogluon+gpt-4o-fallback"
        ? "Local OCR + rules + AutoGluon + GPT-4o fallback"
      : provider === "local-image-metadata"
        ? "Local image metadata"
      : provider === "local-openpyxl"
        ? "Local Excel parser"
        : provider === "local-ollama"
        ? "Ollama Qwen"
        : provider === "template-baseline"
          ? "Template baseline"
        : provider === "local-autogluon"
          ? "AutoGluon Tabular"
        : provider === "local-ocr"
          ? "Local OCR"
          : provider === "autogluon-timeseries"
            ? "AutoGluon TimeSeries"
            : provider === "local-seasonal-baseline"
              ? "Seasonal baseline"
          : provider === "fallback-unavailable"
            ? "Fallback unavailable"
            : provider || "No run";
  return withPrefix ? `Provider: ${label}` : label;
}

function amlRiskClass(riskLevel: string) {
  if (riskLevel === "Critical") return "text-red-300";
  if (riskLevel === "High") return "text-amber-200";
  if (riskLevel === "Medium") return "text-yellow-300";
  return "text-emerald-300";
}

function kycRiskClass(riskLevel: string) {
  if (riskLevel === "Critical") return "text-red-300";
  if (riskLevel === "High") return "text-amber-200";
  if (riskLevel === "Medium") return "text-yellow-300";
  return "text-emerald-300";
}

function emailRiskClass(riskLevel: string) {
  if (riskLevel === "Critical" || riskLevel === "High") return "text-red-300";
  if (riskLevel === "Medium") return "text-amber-200";
  return "text-emerald-300";
}

function formatMoney(value: number) {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "N/A";
  }
  return `${Math.round(value * 100)}%`;
}

function formatDocumentType(value: string) {
  return value
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatDetailValue(value: unknown) {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function ProgressBar({ percent, stage }: { percent: number; stage: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-zinc-400">
        <span className="capitalize">{stage.replaceAll("_", " ")}</span>
        <span>{percent}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

type ModelDomain = "fraud" | "credit";
type MetricKind = "pr_auc" | "roc_auc" | "f1" | "precision" | "recall" | "accuracy";

function classifyDisplayMetric(
  kind: MetricKind,
  value: number | null | undefined,
  mode: ModelDomain,
  context?: { precision?: number | null; recall?: number | null }
) {
  if (mode === "credit" && value != null && !Number.isNaN(value)) {
    if (kind === "roc_auc") {
      if (value >= 0.75) return "good";
      if (value >= 0.65) return "average";
      return "bad";
    }
    if (kind === "pr_auc") {
      if (value >= 0.35) return "good";
      if (value >= 0.22) return "average";
      return "bad";
    }
  }
  return classifyMetricScore(kind, value, context);
}

function MetricScoreLegend({ mode }: { mode: ModelDomain }) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950/80 p-3 text-xs text-zinc-400">
      <p className="font-medium text-zinc-300">Score color guide</p>
      <ul className="mt-2 list-inside list-disc space-y-1">
        {mode === "credit" ? (
          <>
            <li><span className="text-emerald-400">Good</span> - ROC-AUC &gt;= 0.75 or strong threshold metrics</li>
            <li><span className="text-yellow-400">Average</span> - ROC-AUC 0.65-0.75 or moderate threshold metrics</li>
            <li><span className="text-red-400">Bad</span> - weak ranking or poor precision and recall balance</li>
          </>
        ) : (
          <>
            <li>
              <span className="text-emerald-400">Good</span> - score &gt;= {METRIC_GOOD_MIN} (PR-AUC, ROC-AUC, F1,
              precision, recall)
            </li>
            <li>
              <span className="text-yellow-400">Average</span> - score {METRIC_AVERAGE_MIN}-{METRIC_GOOD_MIN}
            </li>
            <li>
              <span className="text-red-400">Bad</span> - score &lt; {METRIC_AVERAGE_MIN}, or accuracy is high but
              precision and recall are both below 15%
            </li>
          </>
        )}
      </ul>
    </div>
  );
}

function EvaluationCharts({ evaluation, mode = "fraud" }: { evaluation: SplitEvaluation; mode?: ModelDomain }) {
  const primaryLabel = evaluation.primary_metric_label ?? "PR-AUC";
  const primaryScoreValue = evaluation.primary_score ?? null;
  const primaryScore =
    primaryScoreValue != null ? primaryScoreValue.toFixed(3) : "N/A";
  const prCurve = evaluation.pr_curve ?? [];
  const metricContext = { precision: evaluation.precision, recall: evaluation.recall };
  const primaryMetricKey: MetricKind = evaluation.primary_metric === "roc_auc" ? "roc_auc" : "pr_auc";
  const secondaryAucValue = mode === "credit" ? evaluation.pr_auc : evaluation.roc_auc;
  const secondaryAucKind: MetricKind = mode === "credit" ? "pr_auc" : "roc_auc";
  const primaryQuality = classifyDisplayMetric(primaryMetricKey, primaryScoreValue, mode, metricContext);
  const precisionQuality = classifyDisplayMetric("precision", evaluation.precision ?? null, mode, metricContext);
  const recallQuality = classifyDisplayMetric("recall", evaluation.recall ?? null, mode, metricContext);
  const f1Quality = classifyDisplayMetric("f1", evaluation.f1 ?? null, mode, metricContext);
  const accuracyQuality = classifyDisplayMetric("accuracy", evaluation.accuracy, mode, metricContext);
  const secondaryAucQuality = classifyDisplayMetric(secondaryAucKind, secondaryAucValue, mode, metricContext);
  const confusionData = [
    { label: "True negative", count: evaluation.confusion_matrix.tn },
    { label: "False positive", count: evaluation.confusion_matrix.fp },
    { label: "False negative", count: evaluation.confusion_matrix.fn },
    { label: "True positive", count: evaluation.confusion_matrix.tp }
  ];

  return (
    <div className="space-y-5">
      <MetricScoreLegend mode={mode} />
      <div
        className={`rounded-lg border p-4 ${
          primaryQuality ? qualityPanelClass(primaryQuality) : "border-zinc-800 bg-zinc-900"
        }`}
      >
        <p className="text-xs uppercase tracking-wide text-zinc-400">Primary model score</p>
        <p
          className={`mt-1 text-2xl font-semibold ${
            primaryQuality ? qualityTextClass(primaryQuality) : "text-zinc-100"
          }`}
        >
          {primaryLabel}: {primaryScore}
          {primaryQuality ? metricQualityLabel(primaryQuality) : ""}
        </p>
        <p className="mt-2 text-sm text-zinc-400">
          {mode === "credit"
            ? "ROC-AUC is used to select and compare credit default ranking quality. PR-AUC and threshold metrics are shown below as operational references."
            : "PR-AUC (average precision) is used to select and compare models on imbalanced fraud data. Accuracy and ROC-AUC are shown below as secondary metrics."}
        </p>
      </div>
      <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
        <MetricCard
          label={`${primaryLabel} (primary)`}
          value={primaryScore}
          quality={primaryQuality}
        />
        <MetricCard
          label="Precision @ threshold"
          value={
            evaluation.precision != null ? `${Math.round(evaluation.precision * 100)}%` : "N/A"
          }
          quality={precisionQuality}
        />
        <MetricCard
          label="Recall @ threshold"
          value={evaluation.recall != null ? `${Math.round(evaluation.recall * 100)}%` : "N/A"}
          quality={recallQuality}
        />
        <MetricCard
          label="F1 @ threshold"
          value={evaluation.f1 != null ? evaluation.f1.toFixed(3) : "N/A"}
          quality={f1Quality}
        />
        <MetricCard
          label="Accuracy (secondary)"
          value={`${Math.round(evaluation.accuracy * 100)}%`}
          quality={accuracyQuality}
        />
        <MetricCard
          label={mode === "credit" ? "PR-AUC (secondary)" : "ROC-AUC (secondary)"}
          value={secondaryAucValue != null ? secondaryAucValue.toFixed(3) : "N/A"}
          quality={secondaryAucQuality}
        />
      </div>
      <p className="text-sm text-zinc-400">
        {evaluation.split.toUpperCase()} split: {evaluation.record_count} records. Operational
        precision/recall/F1 use threshold {evaluation.threshold}; ranking quality uses {primaryLabel}.
      </p>
      <div className="grid grid-cols-2 gap-5">
        <div>
          <h3 className="mb-2 text-sm font-medium text-zinc-300">Precision-Recall Curve</h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={prCurve}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="recall" name="Recall" domain={[0, 1]} />
              <YAxis dataKey="precision" name="Precision" domain={[0, 1]} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="precision" stroke="#34d399" dot={false} name="Precision" />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium text-zinc-300">
            {mode === "credit" ? "ROC Curve (primary ranking)" : "ROC Curve (secondary)"}
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={evaluation.roc_curve}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="fpr" name="FPR" />
              <YAxis dataKey="tpr" name="TPR" domain={[0, 1]} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="tpr" stroke="#10b981" dot={false} name="TPR" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium text-zinc-300">Confusion Matrix @ threshold</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={confusionData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="label" interval={0} angle={-12} textAnchor="end" height={60} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#047857" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

const FRAUD_FEATURE_COLUMNS = [
  "transaction_id",
  "customer_id",
  "account_age_days",
  "amount",
  "currency",
  "merchant_id",
  "merchant_category",
  "merchant_risk_score",
  "channel",
  "transaction_type",
  "card_type",
  "country",
  "is_international",
  "device_trust_score",
  "ip_risk_score",
  "auth_method",
  "device_os",
  "session_duration_minutes",
  "failed_login_count_24h",
  "velocity_24h_count",
  "days_since_last_transaction",
  "prior_chargebacks",
  "hour_of_day",
  "is_new_payee",
  "distance_from_home_km",
  "avg_30d_amount",
  "account_balance_before",
  "label_is_fraud"
] as const;

const FRAUD_PREDICTION_COLUMNS = [
  "prediction_quality",
  "predicted_is_fraud",
  "fraud_probability",
  "risk_level",
  "decision"
] as const;

const CREDIT_FEATURE_COLUMNS = [
  "application_id",
  "customer_id",
  "age",
  "employment_status",
  "employment_years",
  "monthly_income",
  "monthly_expenses",
  "existing_debt",
  "requested_loan_amount",
  "requested_term_months",
  "loan_purpose",
  "home_ownership",
  "credit_history_months",
  "prior_defaults",
  "delinquencies_12m",
  "credit_utilization",
  "savings_balance",
  "checking_balance",
  "num_open_accounts",
  "recent_credit_inquiries",
  "region",
  "channel",
  "collateral_value",
  "label_default_12m",
  "target_loss_given_default"
] as const;

const CREDIT_PREDICTION_COLUMNS = [
  "prediction_quality",
  "predicted_default_12m",
  "pd_probability",
  "risk_grade",
  "decision",
  "recommended_limit",
  "expected_loss"
] as const;

function formatColumnHeader(key: string) {
  return key.replace(/_/g, " ");
}

function formatCellValue(key: string, value: unknown) {
  if (value === null || value === undefined) return "-";
  if (key === "prediction_quality") {
    return String(value);
  }
  if (key === "label_is_fraud" || key === "predicted_is_fraud") {
    return fraudLabel(Number(value));
  }
  if (key === "label_default_12m" || key === "predicted_default_12m") {
    return Number(value) === 1 ? "Default" : "Current";
  }
  if (key === "is_international" || key === "is_new_payee") {
    return Number(value) === 1 ? "Yes" : "No";
  }
  if (key === "fraud_probability" || key === "pd_probability" || key === "credit_utilization" || key === "target_loss_given_default" || key.endsWith("_score")) {
    return Number(value).toFixed(3);
  }
  if (
    key === "amount" ||
    key === "avg_30d_amount" ||
    key === "account_balance_before" ||
    key === "monthly_income" ||
    key === "monthly_expenses" ||
    key === "existing_debt" ||
    key === "requested_loan_amount" ||
    key === "savings_balance" ||
    key === "checking_balance" ||
    key === "collateral_value" ||
    key === "recommended_limit" ||
    key === "expected_loss"
  ) {
    return Number(value).toFixed(2);
  }
  if (typeof value === "number" && !Number.isInteger(value)) {
    return Number(value).toFixed(2);
  }
  return String(value);
}

function isFraudDecision(row: unknown): row is FraudDecision {
  return Boolean(row && typeof row === "object" && "transaction_id" in row);
}

function isCreditDecision(row: unknown): row is CreditDecision {
  return Boolean(row && typeof row === "object" && "application_id" in row);
}

function qualityFromCreditDecision(decision: CreditDecision): "good" | "average" | "bad" {
  if (decision.actual_default_12m !== decision.predicted_default_12m) {
    return "bad";
  }
  const confidence = decision.actual_default_12m === 1 ? decision.pd_probability : 1 - decision.pd_probability;
  if (confidence >= 0.65) return "good";
  if (confidence >= 0.45) return "average";
  return "average";
}

function PredictionQualityLegend() {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950/80 p-3 text-xs text-zinc-400">
      <p className="font-medium text-zinc-300">Prediction quality thresholds</p>
      <ul className="mt-2 list-inside list-disc space-y-1">
        <li>
          <span className="text-emerald-400">Good</span> - predicted label matches actual, confidence &gt;=
          55% (fraud prob &gt;= 0.55 if fraud, else &lt;= 0.45).
        </li>
        <li>
          <span className="text-yellow-400">Average</span> - matches actual, confidence 35-55%.
        </li>
        <li>
          <span className="text-red-400">Bad</span> - predicted label does not match actual (operational
          threshold {OPERATIONAL_THRESHOLD}).
        </li>
      </ul>
    </div>
  );
}

function FraudPredictionTable({
  splitLabel,
  rows,
  evaluation
}: {
  splitLabel: "validation" | "test";
  rows: Record<string, unknown>[];
  evaluation: SplitEvaluation | null;
}) {
  if (!rows.length) {
    return (
      <EmptyState
        text={
          splitLabel === "test"
            ? "No test data is available. Run npm run data:generate and npm run db:seed."
            : "No validation preview is available. Run npm run db:seed after generating data."
        }
      />
    );
  }

  const predictionByTxn = new Map(
    (evaluation?.records ?? []).filter(isFraudDecision).map((row) => [row.transaction_id, row])
  );

  const featureColumns = FRAUD_FEATURE_COLUMNS.filter((key) => key in rows[0]);
  const showPredictions = Boolean(evaluation?.records?.length);

  return (
    <div className="space-y-3">
      <PredictionQualityLegend />
      <p className="text-xs text-zinc-500">
        {splitLabel === "validation" ? "Validation" : "Test"} preview: {rows.length} rows,{" "}
        {featureColumns.length} features
        {showPredictions ? `, predictions colored by quality` : ""}.
        {splitLabel === "test" && !showPredictions ? " Run Fraud Model to score test rows." : ""}
      </p>
      <div className="overflow-x-auto">
        <table className="min-w-max text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-400">
              {featureColumns.map((key) => (
                <th key={key} className="whitespace-nowrap px-3 py-2">
                  {formatColumnHeader(key)}
                </th>
              ))}
              {showPredictions
                ? FRAUD_PREDICTION_COLUMNS.map((key) => (
                    <th key={key} className="whitespace-nowrap bg-zinc-900/80 px-3 py-2 text-emerald-400/90">
                      {formatColumnHeader(key)}
                    </th>
                  ))
                : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const txnId = String(row.transaction_id);
              const predicted = predictionByTxn.get(txnId);
              const quality = predicted ? qualityFromDecision(predicted) : null;
              const qualityClass = quality ? qualityTextClass(quality) : "";

              return (
                <tr key={txnId} className="border-b border-zinc-800/80">
                  {featureColumns.map((key) => (
                    <td key={key} className="whitespace-nowrap px-3 py-2">
                      {formatCellValue(key, row[key])}
                    </td>
                  ))}
                  {showPredictions
                    ? FRAUD_PREDICTION_COLUMNS.map((key) => {
                        if (!predicted) {
                          return (
                            <td key={key} className="whitespace-nowrap bg-zinc-900/40 px-3 py-2">
                              -
                            </td>
                          );
                        }
                        if (key === "prediction_quality") {
                          return (
                            <td key={key} className={`whitespace-nowrap bg-zinc-900/40 px-3 py-2 ${qualityClass}`}>
                              {qualityLabel(quality!)}
                            </td>
                          );
                        }
                        const value =
                          key === "predicted_is_fraud"
                            ? predicted.predicted_is_fraud
                            : key === "fraud_probability"
                              ? predicted.fraud_probability
                              : key === "risk_level"
                                ? predicted.risk_level
                                : predicted.decision;
                        return (
                          <td key={key} className={`whitespace-nowrap bg-zinc-900/40 px-3 py-2 ${qualityClass}`}>
                            {formatCellValue(key, value)}
                          </td>
                        );
                      })
                    : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CreditPredictionQualityLegend() {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950/80 p-3 text-xs text-zinc-400">
      <p className="font-medium text-zinc-300">Decision quality thresholds</p>
      <ul className="mt-2 list-inside list-disc space-y-1">
        <li><span className="text-emerald-400">Good</span> - predicted status matches actual with confidence &gt;= 65%.</li>
        <li><span className="text-yellow-400">Average</span> - predicted status matches actual with confidence 45-65%.</li>
        <li><span className="text-red-400">Bad</span> - predicted default status does not match the synthetic label.</li>
      </ul>
    </div>
  );
}

function CreditRiskPredictionTable({
  splitLabel,
  rows,
  evaluation
}: {
  splitLabel: "validation" | "test";
  rows: Record<string, unknown>[];
  evaluation: SplitEvaluation | null;
}) {
  if (!rows.length) {
    return (
      <EmptyState
        text={
          splitLabel === "test"
            ? "No test data is available. Run npm run data:generate and npm run db:seed."
            : "No validation preview is available. Run npm run db:seed after generating data."
        }
      />
    );
  }

  const predictionByApplication = new Map(
    (evaluation?.records ?? []).filter(isCreditDecision).map((row) => [row.application_id, row])
  );

  const featureColumns = CREDIT_FEATURE_COLUMNS.filter((key) => key in rows[0]);
  const showPredictions = Boolean(evaluation?.records?.length);

  return (
    <div className="space-y-3">
      <CreditPredictionQualityLegend />
      <p className="text-xs text-zinc-500">
        {splitLabel === "validation" ? "Validation" : "Test"} preview: {rows.length} rows,{" "}
        {featureColumns.length} fields
        {showPredictions ? `, decisions colored by quality` : ""}.
        {splitLabel === "test" && !showPredictions ? " Run Credit Risk Model to score test applications." : ""}
      </p>
      <div className="overflow-x-auto">
        <table className="min-w-max text-left text-sm">
          <thead>
            <tr className="border-b border-zinc-800 text-xs uppercase text-zinc-400">
              {featureColumns.map((key) => (
                <th key={key} className="whitespace-nowrap px-3 py-2">
                  {formatColumnHeader(key)}
                </th>
              ))}
              {showPredictions
                ? CREDIT_PREDICTION_COLUMNS.map((key) => (
                    <th key={key} className="whitespace-nowrap bg-zinc-900/80 px-3 py-2 text-emerald-400/90">
                      {formatColumnHeader(key)}
                    </th>
                  ))
                : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const applicationId = String(row.application_id);
              const predicted = predictionByApplication.get(applicationId);
              const quality = predicted ? qualityFromCreditDecision(predicted) : null;
              const qualityClass = quality ? qualityTextClass(quality) : "";

              return (
                <tr key={applicationId} className="border-b border-zinc-800/80">
                  {featureColumns.map((key) => (
                    <td key={key} className="whitespace-nowrap px-3 py-2">
                      {formatCellValue(key, row[key])}
                    </td>
                  ))}
                  {showPredictions
                    ? CREDIT_PREDICTION_COLUMNS.map((key) => {
                        if (!predicted) {
                          return (
                            <td key={key} className="whitespace-nowrap bg-zinc-900/40 px-3 py-2">
                              -
                            </td>
                          );
                        }
                        if (key === "prediction_quality") {
                          return (
                            <td key={key} className={`whitespace-nowrap bg-zinc-900/40 px-3 py-2 ${qualityClass}`}>
                              {qualityLabel(quality!)}
                            </td>
                          );
                        }
                        const value =
                          key === "predicted_default_12m"
                            ? predicted.predicted_default_12m
                            : key === "pd_probability"
                              ? predicted.pd_probability
                              : key === "risk_grade"
                                ? predicted.risk_grade
                                : key === "recommended_limit"
                                  ? predicted.recommended_limit
                                  : key === "expected_loss"
                                    ? predicted.expected_loss
                                    : predicted.decision;
                        return (
                          <td key={key} className={`whitespace-nowrap bg-zinc-900/40 px-3 py-2 ${qualityClass}`}>
                            {formatCellValue(key, value)}
                          </td>
                        );
                      })
                    : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RunHistory({ runs }: { runs: ModelRun[] }) {
  if (!runs.length) {
    return <EmptyState text="No run history yet." />;
  }
  return (
    <div className="grid gap-2">
      {runs.slice(0, 8).map((run) => (
        <div key={run.id} className="grid grid-cols-[1.2fr_0.8fr_0.8fr_1fr] gap-3 rounded-md border border-zinc-800 bg-zinc-950 p-3 text-sm">
          <span className="font-medium">{run.id}</span>
          <span>{run.status}</span>
          <span>{run.provider_used}</span>
          <span className="text-zinc-400">{run.duration_ms ? `${run.duration_ms} ms` : "No duration"}</span>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-zinc-700 bg-zinc-950 p-6 text-sm text-zinc-400">{text}</div>;
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-100">
      {message}
    </div>
  );
}
