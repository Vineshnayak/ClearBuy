import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine import ClearBuyOrchestrator
from models.schemas import RequestRow
from core.financial_math import FinancialEngine
import csv

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hackerrank-orchestrate-september26"))
    truth_file = os.path.join(repo_root, "dataset", "sample_requests.csv")
    orchestrator = ClearBuyOrchestrator(use_mock=True)
    
    with open(truth_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["request_id"] == "request_01":
                r = row.copy()
                r['allows_partial_payment'] = r['allows_partial_payment'].lower() == 'true'
                r['requested_amount'] = float(r['requested_amount'])
                req = RequestRow(
                    request_id=r["request_id"],
                    user_id=r["user_id"],
                    request_date=r["request_date"],
                    request_type=r["request_type"],
                    requested_amount=r["requested_amount"],
                    desired_completion_date=r["desired_completion_date"],
                    allows_partial_payment=r["allows_partial_payment"],
                    request_text=r["request_text"]
                )
                orchestrator.data_loader.requests["request_01"] = req

    data = orchestrator.extractor.process_request_data("request_01")
    engine = FinancialEngine(
        request=data["request"],
        profile=data["profile"],
        events=data["events"],
        payment_options=data["payment_options"],
        exchange_rates=data["exchange_rates"]
    )
    fc = engine.build_base_forecast()
    print("Initial balance:", fc.initial_balance)
    print("Min balance:", fc.min_balance)
    flows = sorted(fc.daily_net.items())
    for d, amt in flows:
        print(f"{d.strftime('%Y-%m-%d')}: {amt}")

if __name__ == "__main__":
    main()
