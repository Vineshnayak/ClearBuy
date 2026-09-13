import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_loader import DataLoader
from core.extractor import PipelineExtractor
from models.schemas import Message

def test_data_loader():
    loader = DataLoader()
    loader.load_all()
    
    # Verify dataset was found and loaded
    assert len(loader.requests) > 0, "No requests loaded. Check DATASET_DIR."
    assert len(loader.profiles) > 0, "No profiles loaded."
    assert len(loader.events) > 0, "No events loaded."
    
    # Grab a request to verify the extractor pipeline
    req_id = list(loader.requests.keys())[0]
    
    extractor = PipelineExtractor(data_loader=loader, use_mock=True)
    result = extractor.process_request_data(req_id)
    
    assert "request" in result
    assert "profile" in result
    assert "events" in result
    assert "payment_options" in result
    
    from models.schemas import FinancialEvent
    loader.events["test_user"] = [
        FinancialEvent(
            event_id="mock_e1",
            user_id="test_user",
            event_type="test",
            description="test event",
            category="test",
            direction="debit",
            amount=None,
            currency="IDR",
            event_date="2025-01-01",
            settlement_date="2025-01-01",
            status="pending",
            linked_event_id=None,
            flexibility="fixed",
            minimum_allowed_amount=None
        )
    ]
    
    # Let's test the mock application logic directly
    extractor = PipelineExtractor(data_loader=loader, use_mock=True)
    msg = Message(
        message_id="m1", 
        user_id="u1", 
        request_id=None, 
        related_event_id="mock_e1", 
        sent_at="2025-01-01", 
        source_type="user", 
        message_text="This event was cancelled."
    )
    
    facts = extractor._extract_from_message(msg)
    assert facts.is_cancelled == True
    
    # Mock apply
    mock_event = loader.events["test_user"][0].model_copy()
    extractor._apply_facts(mock_event, facts)
    assert mock_event.status == "cancelled"
