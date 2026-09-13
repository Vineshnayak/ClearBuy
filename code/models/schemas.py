from pydantic import BaseModel, Field
from typing import Literal, Optional, List

class RequestRow(BaseModel):
    request_id: str
    user_id: str
    request_date: str
    request_type: str
    requested_amount: float
    desired_completion_date: str
    allows_partial_payment: bool
    request_text: str
    
    @property
    def requested_amount_cents(self) -> int:
        return int(round(self.requested_amount * 100))

class OutputRow(BaseModel):
    request_id: str
    amount_safe_to_pay: float = Field(ge=0.0)
    affordability_status: Literal["affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"]
    recommended_payment_method: Literal["full_payment", "partial_payment", "installments", "wait", "not_recommended"]
    payment_plan: str # <YYYY-MM-DD>:<amount>|... or none
    earliest_date_for_full_payment: str # YYYY-MM-DD or empty string
    spending_changes_needed: str # stop:<event_id>|reduce_to:<event_id>:<amount> or none
    decision_explanation: str

class FinancialProfile(BaseModel):
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    financial_priorities: str
    expense_categories_to_protect: str
    expense_categories_user_is_willing_to_reduce: str
    expense_categories_user_is_willing_to_stop: str
    payment_methods_user_will_consider: str
    max_installment_months: Optional[int]
    
    @property
    def current_available_balance_cents(self) -> int:
        return int(round(self.current_available_balance * 100))
        
    @property
    def minimum_balance_to_keep_cents(self) -> int:
        return int(round(self.minimum_balance_to_keep * 100))

class FinancialEvent(BaseModel):
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: Optional[float]
    currency: str
    event_date: str
    settlement_date: str
    status: str
    linked_event_id: Optional[str]
    flexibility: str
    minimum_allowed_amount: Optional[float]
    
    @property
    def amount_cents(self) -> Optional[int]:
        return int(round(self.amount * 100)) if self.amount is not None else None
        
    @property
    def dates_and_amounts(self) -> str:
        if not self.payments: return "none"
        res = []
        for p in self.payments:
            amt_str = f"{p.amount:.2f}".rstrip('0').rstrip('.')
            res.append(f"{p.date}:{amt_str}")
        return "|".join(res)
        
    @property
    def minimum_allowed_amount_cents(self) -> Optional[int]:
        return int(round(self.minimum_allowed_amount * 100)) if self.minimum_allowed_amount is not None else None

class ExchangeRate(BaseModel):
    rate_date: str
    from_currency: str
    to_currency: str
    rate: float

class PaymentOption(BaseModel):
    payment_option_id: str
    request_id: str
    payment_method: str
    payment_amount: float
    number_of_payments: int
    first_payment_date: str
    payment_frequency_days: Optional[int]
    financing_fee: float
    total_payable_amount: float
    
    @property
    def payment_amount_cents(self) -> int:
        return int(round(self.payment_amount * 100))
        
    @property
    def total_payable_amount_cents(self) -> int:
        return int(round(self.total_payable_amount * 100))

class Message(BaseModel):
    message_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    sent_at: str
    source_type: str
    message_text: str

class ImageRecord(BaseModel):
    image_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]

class ExtractedEventFacts(BaseModel):
    is_cancelled: bool = Field(default=False, description="True if the message or image explicitly states the event is cancelled or voided.")
    amended_date: Optional[str] = Field(default=None, description="If the event date was changed, the new date in YYYY-MM-DD format.")
    amended_amount: Optional[float] = Field(default=None, description="If the amount was changed or clarified, the new exact numeric amount.")
    is_confirmed: bool = Field(default=False, description="True if the message confirms a pending or estimate event is now settled or approved.")
