"""
Appends one row per metric to evals/results_log.csv.
Every phase in IMPROVEMENT_PLAN.md logs its before/after numbers here,
immediately after that phase's work is done -- not batched for later.
"""
import csv
import datetime
import os

LOG_PATH = os.path.join(os.path.dirname(__file__), "results_log.csv")
FIELDS = ["date", "experiment", "strategy", "metric_name", "metric_value", "tokens", "latency_ms", "notes"]


def log_result(experiment: str, strategy: str, metric_name: str, metric_value,
               tokens=None, latency_ms=None, notes: str = ""):
    """Appends a single measured result. Creates the log with a header if it doesn't exist yet."""
    file_exists = os.path.isfile(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "date": datetime.date.today().isoformat(),
            "experiment": experiment,
            "strategy": strategy,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "tokens": tokens if tokens is not None else "",
            "latency_ms": latency_ms if latency_ms is not None else "",
            "notes": notes,
        })


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Log one experiment result row.")
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--metric-name", required=True)
    parser.add_argument("--metric-value", required=True)
    parser.add_argument("--tokens", default=None)
    parser.add_argument("--latency-ms", default=None)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    log_result(args.experiment, args.strategy, args.metric_name, args.metric_value,
               args.tokens, args.latency_ms, args.notes)
    print(f"Logged: {args.experiment} / {args.strategy} / {args.metric_name} = {args.metric_value}")
