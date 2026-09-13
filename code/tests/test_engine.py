import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine import ClearBuyOrchestrator
from core.data_loader import DataLoader
from models.schemas import OutputRow

def test_engine_end_to_end_request_01():
    # request_01 is from user_01. It tests full payment capability.
    orchestrator = ClearBuyOrchestrator(use_mock=True)
    
    output = orchestrator.process_request("request_01")
    
    assert isinstance(output, OutputRow)
    assert output.request_id == "request_01"
    assert output.affordability_status == "affordable_now"
    assert output.recommended_payment_method == "full_payment"
    assert output.amount_safe_to_pay == 25256.0
    
    # Check the fallback explanation was used and formatted correctly
    assert "Pay 25256.0 today" in output.decision_explanation

def test_engine_end_to_end_request_02():
    # Try another request if it exists in the sample data, or just ensure process_request doesn't crash
    # We will test request_02
    orchestrator = ClearBuyOrchestrator(use_mock=True)
    try:
        output = orchestrator.process_request("request_02")
        assert isinstance(output, OutputRow)
    except Exception as e:
        # If request_02 doesn't exist or crashes, fail the test
        assert False, f"Failed on request_02: {e}"
