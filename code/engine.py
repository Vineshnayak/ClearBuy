from typing import Optional
from models.schemas import OutputRow
from core.data_loader import DataLoader
from core.extractor import PipelineExtractor
from core.financial_math import FinancialEngine
from core.llm_provider import ExtractorProvider

class ClearBuyOrchestrator:
    def __init__(self, data_loader: Optional[DataLoader] = None, use_mock: bool = False):
        self.data_loader = data_loader or DataLoader()
        if not data_loader:
            self.data_loader.load_all()
            
        self.extractor = PipelineExtractor(self.data_loader, use_mock=use_mock)
        self.llm_provider = ExtractorProvider()
        
        # In mock mode, we force the LLM provider's client to None so it falls back to mock_explanation
        if use_mock:
            self.llm_provider.groq_client = None
            self.llm_provider.gemini_model = None
            
        self.use_mock = use_mock
        
    def process_request(self, request_id: str) -> OutputRow:
        # 1. Extract and resolve data
        data = self.extractor.process_request_data(request_id)
        if not data:
            raise ValueError(f"Request {request_id} not found in loaded data.")
            
        req = data["request"]
        
        # 2. Evaluate mathematically
        engine = FinancialEngine(
            request=req,
            profile=data["profile"],
            events=data["events"],
            payment_options=data["payment_options"],
            exchange_rates=data["exchange_rates"]
        )
        math_result = engine.evaluate()
        
        # 3. Generate explanation
        explanation = self.llm_provider.generate_explanation(req, math_result)
        
        # 4. Construct OutputRow
        return OutputRow(
            request_id=request_id,
            amount_safe_to_pay=math_result["amount_safe_to_pay"],
            affordability_status=math_result["affordability_status"],
            recommended_payment_method=math_result["recommended_payment_method"],
            payment_plan=math_result["payment_plan"],
            earliest_date_for_full_payment=math_result["earliest_date_for_full_payment"],
            spending_changes_needed=math_result["spending_changes_needed"],
            decision_explanation=explanation
        )
