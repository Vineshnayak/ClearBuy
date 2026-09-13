import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.schemas import RequestRow, FinancialProfile, FinancialEvent
from core.financial_math import CashFlowForecast, FinancialEngine

def get_base_req_prof(req_amt=25000, curr_bal=50000, min_bal=10000):
    req = RequestRow(
        request_id="req1",
        user_id="u1",
        request_date="2024-03-01",
        request_type="purchase",
        requested_amount=req_amt,
        desired_completion_date="2024-03-20",
        allows_partial_payment=True,
        request_text="Buy this"
    )
    prof = FinancialProfile(
        user_id="u1",
        home_currency="USD",
        current_available_balance=curr_bal,
        minimum_balance_to_keep=min_bal,
        financial_priorities="",
        expense_categories_to_protect="",
        expense_categories_user_is_willing_to_reduce="",
        expense_categories_user_is_willing_to_stop="",
        payment_methods_user_will_consider="full_payment, partial_payment, installments",
        max_installment_months=None
    )
    return req, prof

def test_immediate_full_payment():
    req, prof = get_base_req_prof(req_amt=20000, curr_bal=50000, min_bal=10000)
    engine = FinancialEngine(req, prof, [], [], [])
    res = engine.evaluate()
    assert res["affordability_status"] == "affordable_now"
    assert res["recommended_payment_method"] == "full_payment"
    assert res["amount_safe_to_pay"] == 20000.0

def test_insufficient_today_but_wait():
    # Only 25k now, min is 10k, needs 20k. Cannot pay today.
    # Future salary on Mar 15 of 20k.
    req, prof = get_base_req_prof(req_amt=20000, curr_bal=25000, min_bal=10000)
    evt = FinancialEvent(
        event_id="e1", user_id="u1", event_type="income", description="salary", category="salary",
        direction="credit", amount=20000, currency="USD", event_date="2024-03-15", settlement_date="2024-03-15",
        status="scheduled", linked_event_id=None, flexibility="fixed", minimum_allowed_amount=None
    )
    engine = FinancialEngine(req, prof, [evt], [], [])
    res = engine.evaluate()
    
    assert res["affordability_status"] == "affordable_later"
    assert res["recommended_payment_method"] == "wait"
    assert res["earliest_date_for_full_payment"] == "2024-03-15"

def test_recurring_expense_reduction():
    # Starts with 50k, needs 30k. Min balance is 10k. 
    # Current margin: 50k - 10k = 40k. Should be safe to pay 30k, leaving 10k.
    # BUT recurring rent of 5k hits every month. So it will go to 5k < 10k.
    req, prof = get_base_req_prof(req_amt=30000, curr_bal=50000, min_bal=10000)
    evts = [
        FinancialEvent(
            event_id=f"e{i}", user_id="u1", event_type="expense", description="rent", category="rent",
            direction="debit", amount=5000, currency="USD", event_date=f"2023-1{i}-05", settlement_date=f"2023-1{i}-05",
            status="settled", linked_event_id=None, flexibility="fixed", minimum_allowed_amount=None
        ) for i in range(1, 3) # Two past events to trigger recurring
    ]
    engine = FinancialEngine(req, prof, evts, [], [])
    res = engine.evaluate()
    
    # Not affordable to pay fully, amount safe to pay today should be capped by the future lowest balance
    assert res["affordability_status"] == "not_affordable"
    # Starting margin = 40k. 3 months of 5k rent = 15k drain.
    # Lowest balance if we pay nothing = 50k - 15k = 35k.
    # Min balance = 10k. So we only have 25k safe to pay.
    assert res["amount_safe_to_pay"] == 25000.0

def test_cashflow_forecast_math():
    fc = CashFlowForecast("2024-03-01", 100000, 10000)
    fc.add_flow("2024-03-10", 20000, "debit") # down to 80000
    fc.add_flow("2024-04-01", 30000, "credit") # up to 110000
    
    lowest = fc.get_lowest_balance()
    assert lowest == 80000
    
    # What if we deducted 80000 on day 1?
    # Bal: 20000 -> 0 -> 30000
    assert not fc.is_safe(initial_deduction=80000) # dips below 10k
    assert fc.is_safe(initial_deduction=70000) # dips to exactly 10k
