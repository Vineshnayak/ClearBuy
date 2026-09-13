import sys
import os
import csv
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine import ClearBuyOrchestrator
from core.financial_math import FinancialEngine

def main():
    orchestrator = ClearBuyOrchestrator(use_mock=True)
                r = row.copy()
                r["allows_partial_payment"] = r["allows_partial_payment"].lower() == "true"
                r["requested_amount"] = float(r["requested_amount"])
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
                orchestrator.data_loader.requests["request_04"] = req

    data = orchestrator.extractor.process_request_data("request_04")
    engine = FinancialEngine(
        request=data["request"],
        profile=data["profile"],
        events=data["events"],
        payment_options=data["payment_options"],
        exchange_rates=data["exchange_rates"]
    )
    fc = engine.build_base_forecast()
    from collections import defaultdict
    groups = defaultdict(list)
    for e in engine.events:
        if e.status in ['cancelled', 'failed', 'estimate']: continue
        if e.amount_cents is None: continue
        d_str = e.settlement_date if e.settlement_date else e.event_date
        if not d_str: continue
        if e.status in ['settled', 'scheduled', 'pending']:
            groups[(e.category, e.direction)].append(e)
            
    for (cat, direction), items in groups.items():
        print(f"Group {cat} {direction}: {len(items)} items")
    print(f"Start balance: {fc.initial_balance}, Min: {fc.min_balance}, Min Projected: {m}")
    print("Amount safe to pay:", engine.calculate_amount_safe_to_pay())
    for p in plans:
        print(p.method, p.dates_and_amounts)

if __name__ == "__main__":
    main()
