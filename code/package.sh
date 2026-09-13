#!/bin/bash

# Ensure output.csv exists
if [ ! -f "../hackerrank-orchestrate-september26/output.csv" ]; then
    echo "Error: output.csv not found in the hackerrank-orchestrate-september26 directory. Did you run main.py?"
    exit 1
fi

# Ensure evaluation/usage_report.md exists
if [ ! -f "evaluation/usage_report.md" ]; then
    echo "Error: evaluation/usage_report.md not found. Ensure main.py ran successfully."
    exit 1
fi

echo "Packaging code.zip..."
# We run from the parent directory to structure the zip nicely
cd ..
zip -r hackerrank-orchestrate-september26/code.zip code/ -x "*.venv*" "*__pycache__*" "*.pytest_cache*" "code/.env" "code/.DS_Store"

echo "Success! Your submission files are ready in hackerrank-orchestrate-september26/:"
echo "- code.zip"
echo "- output.csv"
echo "- log.txt"
