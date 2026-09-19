"""
Reads evals/results_log.csv and prints/writes a Markdown table of results,
grouped by experiment, in the order rows were logged. Paste the output
straight into the README as evidence for each phase in IMPROVEMENT_PLAN.md.
"""
import csv
import os

LOG_PATH = os.path.join(os.path.dirname(__file__), "results_log.csv")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "results_report.md")


def generate_report() -> str:
    if not os.path.isfile(LOG_PATH):
        return "No results logged yet -- results_log.csv does not exist."

    with open(LOG_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return "results_log.csv exists but has no rows yet."

    experiments = {}
    for row in rows:
        experiments.setdefault(row["experiment"], []).append(row)

    lines = ["# ClauseIQ Eval Results", ""]
    for experiment, exp_rows in experiments.items():
        lines.append(f"## {experiment}")
        lines.append("")
        lines.append("| Date | Strategy | Metric | Value | Tokens | Latency (ms) | Notes |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in exp_rows:
            lines.append(
                f"| {row['date']} | {row['strategy']} | {row['metric_name']} | "
                f"{row['metric_value']} | {row['tokens']} | {row['latency_ms']} | {row['notes']} |"
            )
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_report()
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"\nWritten to {REPORT_PATH}")
