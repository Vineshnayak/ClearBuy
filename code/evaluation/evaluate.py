import csv
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine import ClearBuyOrchestrator
from models.schemas import RequestRow

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hackerrank-orchestrate-september26"))
    truth_file = os.path.join(repo_root, "dataset", "sample_requests.csv")
    
    if not os.path.exists(truth_file):
        print(f"Error: {truth_file} not found")
        sys.exit(1)
        
    truth = {}
    print("Initializing orchestrator (mock=True)...")
    orchestrator = ClearBuyOrchestrator(use_mock=True)
    
    with open(truth_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            truth[row["request_id"]] = row
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
            orchestrator.data_loader.requests[r["request_id"]] = req
    
    fields_to_check = [
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment"
    ]
    
    total = len(truth)
    mismatches = 0
    field_errors = {f: 0 for f in fields_to_check}
    
    for req_id, t_row in truth.items():
        try:
            out = orchestrator.process_request(req_id)
        except Exception as e:
            print(f"[{req_id}] CRASH: {e}")
            mismatches += 1
            continue
            
        row_has_error = False
        print(f"\n--- Evaluating {req_id} ---")
        p_row = out.model_dump()
        
        for f in fields_to_check:
            t_val = str(t_row.get(f, "")).strip()
            p_val = str(p_row.get(f, "")).strip()
            
            if f == "amount_safe_to_pay":
                try:
                    if abs(float(t_val) - float(p_val)) > 0.01:
                        print(f"[{req_id}] {f}: expected {t_val}, got {p_val}")
                        field_errors[f] += 1
                        row_has_error = True
                except ValueError:
                    if t_val != p_val:
                        print(f"[{req_id}] {f}: expected {t_val}, got {p_val}")
                        field_errors[f] += 1
                        row_has_error = True
            elif t_val != p_val:
                print(f"[{req_id}] {f}: expected {t_val}, got {p_val}")
                field_errors[f] += 1
                row_has_error = True
                
        if row_has_error:
            mismatches += 1
        else:
            print(f"[{req_id}] MATCH")
            
    print("\n================== SUMMARY ==================")
    print(f"Total Evaluated: {total}")
    print(f"Perfect Matches: {total - mismatches}")
    print(f"Requests with errors: {mismatches}")
    print("Errors by field:")
    for f, count in field_errors.items():
        print(f"  {f}: {count}")

if __name__ == "__main__":
    main()
