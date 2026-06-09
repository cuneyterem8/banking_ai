export type UseCaseStatus = "implemented" | "planned";

export type UseCaseNavItem = {
  slug: string;
  title: string;
  category: string;
  status: UseCaseStatus;
  order: number;
};

export const USE_CASES: UseCaseNavItem[] = [
  { slug: "fraud-detection", title: "Fraud Detection", category: "Risk Operations", status: "implemented", order: 1 },
  { slug: "credit-risk", title: "Credit Risk", category: "Lending", status: "implemented", order: 2 },
  { slug: "document-ocr", title: "Document OCR", category: "Document Intelligence", status: "implemented", order: 3 },
  { slug: "support-chatbot", title: "Support Chatbot", category: "Customer Operations", status: "implemented", order: 4 },
  { slug: "liquidity-forecast", title: "Liquidity Forecast", category: "Treasury Operations", status: "implemented", order: 5 },
  { slug: "aml-monitoring", title: "AML Monitoring", category: "Compliance", status: "implemented", order: 6 },
  { slug: "kyc-kyb", title: "KYC/KYB", category: "Onboarding", status: "implemented", order: 7 },
  { slug: "email-automation", title: "Email Automation", category: "Customer Communications", status: "implemented", order: 8 },
  { slug: "market-intelligence", title: "Market Intelligence", category: "Research", status: "implemented", order: 9 },
  { slug: "workflow-orchestration", title: "Workflow Orchestration", category: "Process Automation", status: "implemented", order: 10 }
];

export function getUseCase(slug: string | undefined): UseCaseNavItem | undefined {
  return USE_CASES.find((item) => item.slug === slug);
}
