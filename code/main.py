import csv
import sys
import os
from config import config
from models.schemas import RequestRow, OutputRow

def process_request(req: RequestRow) -> OutputRow:
    # Placeholder for Module 1 structure
    # Module 2+ will implement:
    # 1. Loading user profile, events, options
    # 2. Extracting image/message details
    # 3. Deterministic 90-day forecast
    # 4. LLM reasoning and explanation
    return OutputRow(
        request_id=req.request_id,
        amount_safe_to_pay=0.0,
        affordability_status="not_affordable",
        recommended_payment_method="not_recommended",
        payment_plan="none",
        earliest_date_for_full_payment="",
        spending_changes_needed="none",
        decision_explanation="Not implemented yet."
    )

def main():
    requests_path = os.path.join(config.DATASET_DIR, "requests.csv")
    if not os.path.exists(requests_path):
        print(f"Error: {requests_path} not found.")
        sys.exit(1)

    print(f"Reading requests from {requests_path}...")
    
    requests = []
    with open(requests_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert raw strings to appropriate types before Pydantic validation
            row['allows_partial_payment'] = row['allows_partial_payment'].lower() == 'true'
            row['requested_amount'] = float(row['requested_amount'])
            requests.append(RequestRow(**row))

    print(f"Loaded {len(requests)} requests. Processing...")

    outputs = []
    for req in requests:
        out = process_request(req)
        outputs.append(out)

    print(f"Writing results to {config.OUTPUT_FILE}...")
    
    # Validate the required exact column output order
    fieldnames = [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation"
    ]
    
    with open(config.OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for out in outputs:
            writer.writerow(out.model_dump())

    print("Done.")

if __name__ == "__main__":
    main()
