from dataclasses import dataclass


@dataclass(frozen=True)
class UseCaseDefinition:
    slug: str
    title: str
    category: str
    description: str
    adapter_type: str
    model_family: str
    status: str
    implementation_order: int


USE_CASES: tuple[UseCaseDefinition, ...] = (
    UseCaseDefinition(
        slug="fraud-detection",
        title="Fraud Detection",
        category="Risk Operations",
        description="Detect high-risk card and transfer transactions from synthetic transactional data.",
        adapter_type="autogluon-tabular",
        model_family="classification",
        status="implemented",
        implementation_order=1,
    ),
    UseCaseDefinition(
        slug="credit-risk",
        title="Credit Risk",
        category="Lending",
        description="Score synthetic loan applications for default probability and recommended limit.",
        adapter_type="autogluon-tabular",
        model_family="classification-regression",
        status="implemented",
        implementation_order=2,
    ),
    UseCaseDefinition(
        slug="document-ocr",
        title="Document OCR",
        category="Document Intelligence",
        description="Extract structured data from synthetic PDF and scanned document artifacts.",
        adapter_type="ocr-local-gpt4o-fallback",
        model_family="document-extraction",
        status="implemented",
        implementation_order=3,
    ),
    UseCaseDefinition(
        slug="support-chatbot",
        title="Support Chatbot",
        category="Customer Operations",
        description="Answer internal support questions from synthetic policy and FAQ documents.",
        adapter_type="ollama-qwen-gpt4o-fallback",
        model_family="rag",
        status="implemented",
        implementation_order=4,
    ),
    UseCaseDefinition(
        slug="liquidity-forecast",
        title="Liquidity Forecast",
        category="Treasury Operations",
        description="Forecast synthetic branch and ATM cash demand with quantile outputs.",
        adapter_type="autogluon-timeseries",
        model_family="time-series",
        status="implemented",
        implementation_order=5,
    ),
    UseCaseDefinition(
        slug="aml-monitoring",
        title="AML Monitoring",
        category="Compliance",
        description="Prioritize synthetic AML alerts and draft suspicious activity narratives.",
        adapter_type="autogluon-tabular-local-llm-gpt4o-fallback",
        model_family="risk-scoring-reporting",
        status="implemented",
        implementation_order=6,
    ),
    UseCaseDefinition(
        slug="kyc-kyb",
        title="KYC/KYB",
        category="Onboarding",
        description="Verify synthetic customer and company onboarding documents.",
        adapter_type="ocr-rules-autogluon-gpt4o-fallback",
        model_family="document-risk-scoring",
        status="implemented",
        implementation_order=7,
    ),
    UseCaseDefinition(
        slug="email-automation",
        title="Email Automation",
        category="Customer Communications",
        description="Generate compliant synthetic customer email and notification drafts.",
        adapter_type="template-rules-ollama-gpt4o-fallback",
        model_family="draft-generation-compliance",
        status="implemented",
        implementation_order=8,
    ),
    UseCaseDefinition(
        slug="market-intelligence",
        title="Market Intelligence",
        category="Research",
        description="Run budget-controlled multi-agent market research with live web search and cited banking impact briefs.",
        adapter_type="multi-agent-openai-web-search",
        model_family="agentic-research",
        status="implemented",
        implementation_order=9,
    ),
    UseCaseDefinition(
        slug="workflow-orchestration",
        title="Workflow Orchestration",
        category="Process Automation",
        description="Coordinate synthetic onboarding and lending workflow steps across adapters.",
        adapter_type="orchestration",
        model_family="multi-step-agent",
        status="planned",
        implementation_order=10,
    ),
)


def get_use_case(slug: str) -> UseCaseDefinition | None:
    return next((item for item in USE_CASES if item.slug == slug), None)
