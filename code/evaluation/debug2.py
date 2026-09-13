import csv
with open("../hackerrank-orchestrate-september26/dataset/financial_events.csv", "r") as f:
    r = csv.DictReader(f)
    for row in r:
        if row["user_id"] == "user_04":
            print(row['event_date'], row['description'], row['amount'], row['direction'], row['status'])
