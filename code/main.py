import csv
import sys
import os
import argparse
from typing import List

from config import config
from models.schemas import RequestRow, OutputRow
from engine import ClearBuyOrchestrator

def main():
    parser = argparse.ArgumentParser(description="Run the ClearBuy batch orchestrator.")
    parser.add_argument("--mock", action="store_true", help="Run with mock LLM responses to save time/credits")
    parser.add_argument("--request_id", type=str, help="Process and display a single request interactively")
    args = parser.parse_args()

    requests_path = os.path.join(config.DATASET_DIR, "requests.csv")
    if not os.path.exists(requests_path):
        print(f"Error: {requests_path} not found.")
        sys.exit(1)

    if not args.request_id:
        print(f"Reading requests from {requests_path}...")
    
    requests = []
    with open(requests_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if args.request_id and row['request_id'] != args.request_id:
                continue
            row['allows_partial_payment'] = row['allows_partial_payment'].lower() == 'true'
            row['requested_amount'] = float(row['requested_amount'])
            requests.append(RequestRow(**row))

    if args.request_id and not requests:
        print(f"Error: Request ID {args.request_id} not found.")
        sys.exit(1)

    if not args.request_id:
        print(f"Loaded {len(requests)} requests. Initializing orchestrator (mock={args.mock})...")
    orchestrator = ClearBuyOrchestrator(use_mock=args.mock)

    outputs: List[OutputRow] = []
    failed_requests = []

    for req in requests:
        try:
            out = orchestrator.process_request(req.request_id)
            
            # Additional Validations on output
            if out.amount_safe_to_pay < 0 or out.amount_safe_to_pay > req.requested_amount:
                raise ValueError(f"amount_safe_to_pay {out.amount_safe_to_pay} is invalid")
            if out.affordability_status not in ["affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"]:
                raise ValueError(f"Invalid status {out.affordability_status}")
                
            outputs.append(out)
            
            if args.request_id:
                print(f"\n======================================")
                print(f"Request: {req.request_id} ({req.request_type})")
                print(f"Amount: {req.requested_amount}")
                print(f"======================================")
                print(f"Status: {out.affordability_status}")
                print(f"Recommended Method: {out.recommended_payment_method}")
                print(f"Amount Safe To Pay: {out.amount_safe_to_pay}")
                print(f"Payment Plan: {out.payment_plan}")
                print(f"Earliest Full Payment: {out.earliest_date_for_full_payment}")
                print(f"Spending Changes: {out.spending_changes_needed}")
                print(f"======================================")
                print(f"Explanation: {out.decision_explanation}")
                print(f"======================================\n")
                
        except Exception as e:
            print(f"Error processing {req.request_id}: {e}")
            failed_requests.append(req.request_id)
            # Create a fallback OutputRow so the batch isn't strictly smaller than input
            outputs.append(OutputRow(
                request_id=req.request_id,
                amount_safe_to_pay=0.0,
                affordability_status="not_affordable",
                recommended_payment_method="not_recommended",
                payment_plan="none",
                earliest_date_for_full_payment="",
                spending_changes_needed="none",
                decision_explanation=f"Error: {str(e)}"
            ))

    if args.request_id:
        return

    print(f"Finished processing. Processed {len(outputs)}/{len(requests)} requests.")
    if failed_requests:
        print(f"Warning: {len(failed_requests)} requests failed and used fallback outputs.")
        
    print(f"Writing results to {config.OUTPUT_FILE}...")
    
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

    print("Generating usage report...")
    usage_stats = orchestrator.llm_provider.usage_stats
    groq_cost = (usage_stats["groq_prompt_tokens"] * 0.05 / 1e6) + (usage_stats["groq_completion_tokens"] * 0.08 / 1e6)
    gemini_cost = (usage_stats["gemini_prompt_tokens"] * 3.5 / 1e6) + (usage_stats["gemini_completion_tokens"] * 10.5 / 1e6)
    total_cost = groq_cost + gemini_cost
    
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation", "usage_report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("# ClearBuy Token Usage Report\n\n")
        f.write("## Groq (Text & Reasoning)\n")
        f.write(f"- **Requests:** {usage_stats['groq_requests']}\n")
        f.write(f"- **Prompt Tokens:** {usage_stats['groq_prompt_tokens']}\n")
        f.write(f"- **Completion Tokens:** {usage_stats['groq_completion_tokens']}\n")
        f.write(f"- **Cost:** ${groq_cost:.4f}\n\n")
        f.write("## Gemini (Image Extraction)\n")
        f.write(f"- **Requests:** {usage_stats['gemini_requests']}\n")
        f.write(f"- **Prompt Tokens:** {usage_stats['gemini_prompt_tokens']}\n")
        f.write(f"- **Completion Tokens:** {usage_stats['gemini_completion_tokens']}\n")
        f.write(f"- **Cost:** ${gemini_cost:.4f}\n\n")
        f.write("## Totals\n")
        f.write(f"- **Total Estimated Cost:** ${total_cost:.4f}\n")
        
    print(f"Batch runner completed successfully. Estimated cost: ${total_cost:.4f}")

if __name__ == "__main__":
    main()
