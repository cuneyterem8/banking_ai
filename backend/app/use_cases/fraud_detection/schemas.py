from pydantic import BaseModel, Field


class FraudTransaction(BaseModel):
    transaction_id: str
    customer_id: str
    account_age_days: int
    amount: float
    currency: str
    merchant_id: str
    merchant_category: str
    merchant_risk_score: float = Field(ge=0, le=1)
    channel: str
    transaction_type: str
    card_type: str
    country: str
    is_international: int = Field(ge=0, le=1)
    device_trust_score: float = Field(ge=0, le=1)
    ip_risk_score: float = Field(ge=0, le=1)
    auth_method: str
    device_os: str
    session_duration_minutes: int
    failed_login_count_24h: int
    velocity_24h_count: int
    days_since_last_transaction: int
    prior_chargebacks: int
    hour_of_day: int = Field(ge=0, le=23)
    is_new_payee: int = Field(ge=0, le=1)
    distance_from_home_km: float
    avg_30d_amount: float
    account_balance_before: float
    label_is_fraud: int = Field(ge=0, le=1)


class FraudDecision(BaseModel):
    transaction_id: str
    customer_id: str
    amount: float
    actual_is_fraud: int = Field(ge=0, le=1)
    predicted_is_fraud: int = Field(ge=0, le=1)
    fraud_probability: float = Field(ge=0, le=1)
    risk_level: str
    decision: str
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
    precision: float
    recall: float
    f1: float
    accuracy: float
    roc_auc: float | None = None
    threshold: float
    correct_predictions: int
    confusion_matrix: ConfusionMatrix
    pr_curve: list[PrPoint]
    roc_curve: list[RocPoint]
    records: list[FraudDecision]


class FraudRunPayload(BaseModel):
    provider_used: str
    model_name: str
    threshold: float
    split: str
    evaluation: SplitEvaluation


class FraudRunSummary(BaseModel):
    records_processed: int
    high_risk_count: int
    review_count: int
    average_fraud_probability: float
