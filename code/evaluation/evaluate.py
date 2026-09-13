import csv
import sys
import os
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from engine import ClearBuyOrchestrator
from models.schemas import RequestRow

class Evaluator:
    def __init__(self, truth_file: str):
        self.truth_file = truth_file
        self.truth: Dict[str, Dict[str, Any]] = {}
        self.fields_to_check = [
            "amount_safe_to_pay",
            "affordability_status",
            "recommended_payment_method",
            "payment_plan",
            "earliest_date_for_full_payment"
        ]
        self.diagnostics = []
        self.orchestrator = ClearBuyOrchestrator(use_mock=True)

    def load_ground_truth(self):
        if not os.path.exists(self.truth_file):
            raise FileNotFoundError(f"Truth file not found: {self.truth_file}")
            
        with open(self.truth_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.truth[row["request_id"]] = row
                
                # Mock injecting into dataloader so engine can access it
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
                self.orchestrator.data_loader.requests[r["request_id"]] = req
                
    def compare_outputs(self, req_id: str, t_row: dict, p_row: dict) -> List[dict]:
        errors = []
        for f in self.fields_to_check:
            t_val = str(t_row.get(f, "")).strip()
            p_val = str(p_row.get(f, "")).strip()
            
            if f == "amount_safe_to_pay":
                try:
                    if abs(float(t_val) - float(p_val)) > 0.01:
                        errors.append({"field": f, "expected": t_val, "got": p_val})
                except ValueError:
                    if t_val != p_val:
                        errors.append({"field": f, "expected": t_val, "got": p_val})
            elif t_val != p_val:
                errors.append({"field": f, "expected": t_val, "got": p_val})
        return errors

    def evaluate_batch(self):
        self.diagnostics = []
        for req_id, t_row in self.truth.items():
            try:
                out = self.orchestrator.process_request(req_id)
                p_row = out.model_dump()
                errors = self.compare_outputs(req_id, t_row, p_row)
                self.diagnostics.append({
                    "request_id": req_id,
                    "status": "ERROR" if errors else "MATCH",
                    "errors": errors
                })
            except Exception as e:
                self.diagnostics.append({
                    "request_id": req_id,
                    "status": "CRASH",
                    "error_msg": str(e)
                })
                
    def generate_report(self):
        total = len(self.diagnostics)
        crashes = len([d for d in self.diagnostics if d["status"] == "CRASH"])
        matches = len([d for d in self.diagnostics if d["status"] == "MATCH"])
        mismatches = total - crashes - matches
        
        field_errors = {f: 0 for f in self.fields_to_check}
        for d in self.diagnostics:
            if d["status"] == "ERROR":
                for err in d.get("errors", []):
                    field_errors[err["field"]] += 1
                    
        print("\n================== SUMMARY ==================")
        print(f"Total Evaluated: {total}")
        print(f"Perfect Matches: {matches}")
        print(f"Requests with errors: {mismatches}")
        print(f"Crashes: {crashes}")
        print("Errors by field:")
        for f, count in field_errors.items():
            print(f"  {f}: {count}")

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hackerrank-orchestrate-september26"))
    truth_file = os.path.join(repo_root, "dataset", "sample_requests.csv")
    
    evaluator = Evaluator(truth_file)
    evaluator.load_ground_truth()
    print("Evaluating...")
    evaluator.evaluate_batch()
    evaluator.generate_report()

if __name__ == "__main__":
    main()
