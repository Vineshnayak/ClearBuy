import os
import sys
import collections
import csv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine import ClearBuyOrchestrator
from core.financial_math import FinancialEngine

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hackerrank-orchestrate-september26"))
    truth_file = os.path.join(repo_root, "dataset", "sample_requests.csv")
    
    orchestrator = ClearBuyOrchestrator(use_mock=True)
    orchestrator = ClearBuyOrchestrator(use_mock=True)
    with open(truth_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["request_id"] == "request_21":
                r = row.copy()
                r['allows_partial_payment'] = r['allows_partial_payment'].lower() == 'true'
                r['requested_amount'] = float(r['requested_amount'])
                from models.schemas import RequestRow
                orchestrator.data_loader.requests["request_21"] = RequestRow(**r)
                break
    req_id = "request_21"
    
    data = orchestrator.extractor.process_request_data(req_id)
    engine = FinancialEngine(
        request=data["request"],
        profile=data["profile"],
        events=data["events"],
        payment_options=data["payment_options"],
        exchange_rates=data["exchange_rates"]
    )
    
    fc = engine.build_base_forecast()
    print(f"Start date: {fc.start_date}, End date: {fc.end_date}")
    for date in sorted(fc.daily_net.keys()):
        print(date, fc.daily_net[date])
        
    safe = engine.calculate_amount_safe_to_pay()
    print("Safe calculated:", safe)
    
    out = orchestrator.process_request(req_id)
    print("Orchestrator returned safe amount:", out.amount_safe_to_pay)

if __name__ == "__main__":
    main()
