from app.schemas.base import CamelModel


class UsageByModel(CamelModel):
    model_id: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    calls: int


class UsageSummaryOut(CamelModel):
    total_used: int
    total_budget: int
    percent_used: float
    sessions: int
