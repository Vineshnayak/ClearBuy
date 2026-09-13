import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine import ClearBuyOrchestrator
from core.data_loader import DataLoader
from models.schemas import OutputRow

def test_engine_end_to_end_request_01():
    orchestrator = ClearBuyOrchestrator(use_mock=True)
    req_id = list(orchestrator.data_loader.requests.keys())[0]
    output = orchestrator.process_request(req_id)
    
    assert isinstance(output, OutputRow)
    assert output.request_id == req_id
    assert hasattr(output, "affordability_status")
    
def test_engine_end_to_end_request_02():
    orchestrator = ClearBuyOrchestrator(use_mock=True)
    req_id = list(orchestrator.data_loader.requests.keys())[1]
    try:
        output = orchestrator.process_request(req_id)
        assert isinstance(output, OutputRow)
    except Exception as e:
        assert False, f"Failed on {req_id}: {e}"
