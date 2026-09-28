"""Print paper survey tables from the released CSV files; Python standard library only."""

import argparse
import csv
from collections import Counter
from pathlib import Path


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def print_table(title, rows, categories):
    """Use rows as the denominator, including uncertain labels where present."""
    per_server = Counter(row["server"] for row in rows)
    print(f"\n### {title}\n")
    print("| Measure | Paths | Path-weighted | Server-equal | Servers in mean |")
    print("|---|---:|---:|---:|---:|")
    for label, field, value in categories:
        selected = Counter(row["server"] for row in rows if row[field] == value)
        count = sum(selected.values())
        weighted = f"{100 * count / len(rows):.2f}%" if rows else "undefined"
        equal = (
            f"{100 * sum(selected[server] / total for server, total in per_server.items()) / len(per_server):.2f}%"
            if per_server else "undefined"
        )
        print(f"| {label} | {count}/{len(rows)} | {weighted} | {equal} | {len(per_server)} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    folder = Path(__file__).resolve().parent
    servers = read_csv(folder / "servers.csv")
    errors = read_csv(folder / "error_messages.csv")
    advice = [row for row in errors if row["has_next_step"] == "yes"]
    names = {row["name"] for row in servers}
    if len(names) != len(servers) or any(row["server"] not in names for row in errors):
        raise ValueError("Server identifiers must be unique and every error must join a server.")
    if len({row["id"] for row in errors}) != len(errors):
        raise ValueError("Failure-path identifiers must be unique.")

    print("# Table 1 - mainstream\n")
    nonempty = len({row["server"] for row in errors})
    print(f"Repositories: {len(servers)}; eligible failure paths: {len(errors)}; advice paths: {len(advice)}.")
    print(f"Repositories with paths: {nonempty}; zero-path repositories excluded from path-rate means: {len(servers) - nonempty}.")
    print("Server-equal means average within-server proportions; advice analyses exclude servers with no advice paths.")
    print_table("Failure-path characteristics", errors, [
        ("Cause stated", "states_cause", "yes"),
        ("Cause partial", "states_cause", "partial"),
        ("Cause absent", "states_cause", "no"),
        ("Next-step advice", "has_next_step", "yes"),
        ("Stack or internal details", "includes_stack_or_internal", "yes"),
    ])
    print_table("Advice dependence (advice paths only)", advice, [
        ("Caller-dependent", "depends_on_caller_state", "yes"),
        ("Not caller-dependent", "depends_on_caller_state", "no"),
        ("Uncertain", "depends_on_caller_state", "uncertain"),
    ])
    kinds = (
        "format_correction", "wait_retry", "other_tool", "reauthentication",
        "configuration", "contact_human", "other",
    )
    print_table("Advice types (first executable action; advice paths only)", advice,
                [(kind, "next_step_type", kind) for kind in kinds])

    print("\n### Credential, permission and rate-limit failures\n")
    print("| Class | Paths | With next step | Caller-dependent step | Servers with a caller-dependent step |")
    print("|---|---:|---:|---:|---:|")
    for label, classes in (("credentials", {"credentials"}), ("permission", {"permission"}), ("rate_limit", {"rate_limit"}),
                           ("all three", {"credentials", "permission", "rate_limit"})):
        paths = [row for row in errors if row["failure_class"] in classes]
        steps = [row for row in paths if row["has_next_step"] == "yes"]
        dependent = [row for row in steps if row["depends_on_caller_state"] == "yes"]
        print(f"| {label} | {len(paths)} | {len(steps)} | {len(dependent)} | {len({row['server'] for row in dependent})} of {len(servers)} |")

    print("\n### What the caller-dependent steps of these three classes ask the reader to do\n")
    print("| Step requires | Steps | Servers |\n|---|---:|---:|")
    for kind in ("command", "configuration", "web_or_account", "wait_retry", "other_tool", "other"):
        rows = [row for row in errors if row["step_requires"] == kind]
        print(f"| {kind} | {len(rows)} | {len({row['server'] for row in rows})} |")
    waits = [row for row in errors if row["failure_class"] == "rate_limit" and row["next_step_type"] == "wait_retry"]
    print(f"\nRate-limit paths whose next step is to wait and retry: {len(waits)} in {len({row['server'] for row in waits})} servers.")


if __name__ == "__main__":
    main()
