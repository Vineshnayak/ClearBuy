import os
from typing import List, Dict, Optional
from models.schemas import RequestRow, FinancialEvent, Message, ImageRecord, ExtractedEventFacts
from core.data_loader import DataLoader
from core.llm_provider import ExtractorProvider
from config import config

class PipelineExtractor:
    def __init__(self, data_loader: DataLoader, use_mock: bool = False):
        self.data_loader = data_loader
        self.provider = ExtractorProvider()
        self.use_mock = use_mock

    def process_request_data(self, request_id: str) -> Dict:
        """
        Gathers and resolves all data for a request.
        Returns a dictionary containing the validated/resolved facts needed for the engine.
        """
        req = self.data_loader.requests.get(request_id)
        if not req:
            raise ValueError(f"Request {request_id} not found.")
            
        user_id = req.user_id
        profile = self.data_loader.profiles.get(user_id)
        
        # Get raw events
        raw_events = self.data_loader.events.get(user_id, [])
        resolved_events = []
        
        for event in raw_events:
            # Create a copy so we don't mutate the globally loaded dataset
            resolved_event = event.model_copy()
            
            # Check for linked messages
            msgs = self.data_loader.messages.get(event.event_id, [])
            for msg in msgs:
                facts = self._extract_from_message(msg)
                if facts:
                    self._apply_facts(resolved_event, facts)
            
            # Check for linked images (especially if amount is None)
            imgs = self.data_loader.images.get(event.event_id, [])
            for img in imgs:
                facts = self._extract_from_image(img)
                if facts:
                    self._apply_facts(resolved_event, facts)
                    
            resolved_events.append(resolved_event)
            
        # Get payment options for this request
        options = self.data_loader.payment_options.get(request_id, [])
        
        # Get exchange rates
        rates = self.data_loader.exchange_rates
        
        return {
            "request": req,
            "profile": profile,
            "events": resolved_events,
            "payment_options": options,
            "exchange_rates": rates
        }
        
    def _extract_from_message(self, msg: Message) -> Optional[ExtractedEventFacts]:
        if self.use_mock:
            return self.provider.mock_extract(msg.message_text)
        return self.provider.extract_from_text(msg.message_text)
        
    def _extract_from_image(self, img: ImageRecord) -> Optional[ExtractedEventFacts]:
        # Construct path: <dataset_dir>/media/images/<image_id>.png
        image_path = os.path.join(config.DATASET_DIR, "media", "images", f"{img.image_id}.png")
        if self.use_mock:
            return self.provider.mock_extract(image_path)
        return self.provider.extract_from_image(image_path)
        
    def _apply_facts(self, event: FinancialEvent, facts: ExtractedEventFacts):
        """
        Applies conflict resolution rules from extracted facts to the event.
        - explicit cancellations take priority.
        - newer records (amendments) overwrite.
        """
        if facts.is_cancelled:
            event.status = "cancelled"
        if facts.amended_amount is not None:
            event.amount = facts.amended_amount
        if facts.amended_date is not None:
            # Overwrite the dates if amended
            event.event_date = facts.amended_date
            event.settlement_date = facts.amended_date
        if facts.is_confirmed:
            event.status = "settled"
