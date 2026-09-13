import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.schemas import OutputRow, RequestRow

def test_imports():
    # Simple test to verify environment and schemas
    req = RequestRow(
        request_id="req_1",
        user_id="user_1",
        request_date="2026-09-01",
        request_type="purchase",
        requested_amount=100.0,
        desired_completion_date="2026-09-10",
        allows_partial_payment=False,
        request_text="Can I afford this?"
    )
    assert req.request_id == "req_1"

    out = OutputRow(
        request_id="req_1",
        amount_safe_to_pay=0.0,
        affordability_status="not_affordable",
        recommended_payment_method="not_recommended",
        payment_plan="none",
        earliest_date_for_full_payment="",
        spending_changes_needed="none",
        decision_explanation="Test"
    )
    assert out.affordability_status == "not_affordable"
