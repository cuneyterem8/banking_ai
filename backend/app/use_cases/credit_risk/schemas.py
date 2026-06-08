from pydantic import BaseModel, Field


class CreditApplication(BaseModel):
    application_id: str
    customer_id: str
    age: int = Field(ge=18, le=80)
    employment_status: str
    employment_years: float
    monthly_income: float
    monthly_expenses: float
    existing_debt: float
    requested_loan_amount: float
    requested_term_months: int
    loan_purpose: str
    home_ownership: str
    credit_history_months: int
    prior_defaults: int
    delinquencies_12m: int
    credit_utilization: float = Field(ge=0, le=1.5)
    savings_balance: float
    checking_balance: float
    num_open_accounts: int
    recent_credit_inquiries: int
    region: str
    channel: str
    collateral_value: float
    label_default_12m: int = Field(ge=0, le=1)
    target_loss_given_default: float = Field(ge=0, le=1)


class CreditDecision(BaseModel):
    application_id: str
    customer_id: str
    requested_loan_amount: float
    actual_default_12m: int = Field(ge=0, le=1)
    predicted_default_12m: int = Field(ge=0, le=1)
    pd_probability: float = Field(ge=0, le=1)
    risk_grade: str
    decision: str
    recommended_limit: float
    expected_loss: float
    top_factors: list[str]


class ConfusionMatrix(BaseModel):
    tp: int
    tn: int
    fp: int
    fn: int


class RocPoint(BaseModel):
    threshold: float
    tpr: float
    fpr: float


class PrPoint(BaseModel):
    threshold: float
    precision: float
    recall: float


class SplitEvaluation(BaseModel):
    split: str
    record_count: int
    primary_metric: str
    primary_metric_label: str
    primary_score: float | None = None
    pr_auc: float | None = None
    precision: float
    recall: float
    f1: float
    accuracy: float
    threshold: float
    correct_predictions: int
    confusion_matrix: ConfusionMatrix
    pr_curve: list[PrPoint]
    roc_curve: list[RocPoint]
    records: list[CreditDecision]
