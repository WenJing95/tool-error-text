"""Compute the result tables from the run records and print the numbers behind paper Tables 4 to 6.

Requires NumPy. Writes experiment/results/recovery.csv, behaviour.csv, filter.csv,
before_after.csv and contrasts.csv.
The unit of analysis is the scenario (mean of its three runs); intervals are 95% percentile
intervals from a scenario bootstrap stratified by failure type, with the same resampled
scenarios used for every condition and contrast of a model.
"""
import csv
import json
import math
import unicodedata
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODELS = ("gpt-5.5", "gpt-5.6-sol", "gpt-6-sol", "gpt-6-astra", "gpt-6-luna")
REPEATS = 3
VARIANTS = ("A", "C", "D1", "D2", "E1", "E2")
FAILURES = ("unit_format", "missing_field", "wrong_tool", "expired_auth", "missing_resource", "permission_denied", "quota_exhausted")
INVISIBLE = ("expired_auth", "permission_denied", "quota_exhausted")  # failures the agent cannot see in its own call
DRAWS = 10000
SEED = 20260925
HANDLING = ("called_suggested_tool", "asked_user_to_act", "ignored_or_ended")
FILTER_MODEL = "gpt-6-luna"
FILTERED = ("D1f", "D2f", "E1f", "E2f")  # texts D1, D2, E1 and E2 of the expired-credential scenarios after filtering
POOLED = "mean of five models"
# problem A: a step outside the agent's tools on expired credentials; problem B: a bare wait-and-retry on a rate limit
BEFORE_AFTER = (("A", "expired_auth", ("E2", "C", "D2", "E2f")), ("B", "quota_exhausted", ("D1", "D2")))


def jsonl(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def bootstrap_indices(scenes):
    rng = np.random.default_rng(SEED)
    groups, draws = {}, {}
    for failure in FAILURES:
        idx = np.array([i for i, s in enumerate(scenes) if s["failure_type"] == failure])
        groups[failure] = idx
        draws[failure] = idx[rng.integers(0, len(idx), size=(DRAWS, len(idx)))]
    groups["all"] = np.arange(len(scenes))
    draws["all"] = np.concatenate([draws[f] for f in FAILURES], axis=1)
    groups["invisible"] = np.concatenate([groups[f] for f in INVISIBLE])
    draws["invisible"] = np.concatenate([draws[f] for f in INVISIBLE], axis=1)
    return groups, draws


def interval(values):
    return tuple(float(x) for x in np.quantile(values, [0.025, 0.975]))


def stat(values, ids, draws):
    low, high = interval(values[draws].mean(axis=1))
    return dict(estimate=float(values[ids].mean()), ci_low=low, ci_high=high, n_scenarios=len(ids))


def write_csv(path, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalize_filter_text(text):
    """Drop whitespace and punctuation; keep case and other symbols."""
    return "".join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith("P"))


def filter_scores(case, output):
    """Whether every marked step is absent from the output and every other fragment of the message is present."""
    advice, rest, cursor = [], [], 0
    for start, end in case["advice_spans"]:
        rest.append(case["text"][cursor:start])
        advice.append(case["text"][start:end])
        cursor = end
    rest.append(case["text"][cursor:])
    normalized = normalize_filter_text(output)
    marked = [normalize_filter_text(part) for part in advice]
    kept = [normalize_filter_text(part) for part in rest]
    return all(part not in normalized for part in marked if part), all(part in normalized for part in kept if part)


def analyze(scenes, filters, trials, outputs):
    groups, draws = bootstrap_indices(scenes)
    recovery, behaviours, filtering, correct_gain, unavailable_loss = [], [], [], [], {}
    for model in MODELS:
        cube = np.array([[[trials[(model, s["id"], v, r)]["recovered"] for r in range(1, REPEATS + 1)] for v in VARIANTS] for s in scenes], dtype=float)
        means = cube.mean(axis=2)
        values = {v: means[:, j] for j, v in enumerate(VARIANTS)}
        values["D"] = (values["D1"] + values["D2"]) / 2
        values["E"] = (values["E1"] + values["E2"]) / 2
        correct_gain.append(values["D"] - values["C"])
        unavailable_loss[model] = values["C"] - values["E2"]
        for failure, ids in groups.items():
            index = draws[failure]
            for condition, data in values.items():
                variants = (condition,) if condition in VARIANTS else (condition + "1", condition + "2")
                recovery.append(dict(model=model, failure_type=failure, condition=condition, contrast="", n_trials=len(ids) * REPEATS * len(variants), **stat(data, ids, index)))
            for left, right in (("C", "A"), ("D", "C"), ("E", "C"), ("E1", "C"), ("E2", "C")):
                n_trials = len(ids) * REPEATS * (3 if left in ("D", "E") else 2)
                recovery.append(dict(model=model, failure_type=failure, condition="", contrast=left + "-" + right, n_trials=n_trials, **stat(values[left] - values[right], ids, index)))
        for variant in VARIANTS:
            per_scene = [[trials[(model, s["id"], variant, r)]["behaviour"] for r in range(1, REPEATS + 1)] for s in scenes]
            metrics = [("", field, lambda row, f=field: row[f]) for field in ("tool_calls", "repeated_failed_call", "asked_user", "ended_incomplete")]
            targets = ("E1", "E2") if variant == "C" else (variant,) if variant.startswith("E") else ()
            for target in targets:
                field = target.lower() + "_handling"
                for category in HANDLING:
                    metrics.append((target, category, lambda row, f=field, c=category: row[f] == c))
            for target, measure, fn in metrics:
                data = np.array([np.mean([fn(row) for row in rows]) for rows in per_scene])
                for failure, ids in groups.items():
                    behaviours.append(dict(model=model, failure_type=failure, variant=variant, target_advice=target, measure=measure, n_trials=len(ids) * REPEATS, **stat(data, ids, draws[failure])))
    for failure in ("invisible", "expired_auth"):
        ids = groups[failure]
        recovery.append(dict(model=POOLED, failure_type=failure, condition="", contrast="D-C", n_trials=len(ids) * REPEATS * 3 * len(MODELS),
                             **stat(np.mean(correct_gain, axis=0), ids, draws[failure])))
    ids = groups["expired_auth"]  # paired: both models use the same resampled scenarios
    recovery.append(dict(model="gpt-6-astra minus gpt-5.5", failure_type="expired_auth", condition="", contrast="C-E2", n_trials=len(ids) * REPEATS * 2 * 2,
                         **stat(unavailable_loss["gpt-6-astra"] - unavailable_loss["gpt-5.5"], ids, draws["expired_auth"])))
    scores = []
    for case in filters:
        removed, kept = filter_scores(case, outputs[case["id"]])
        scores.append((bool(case["advice_spans"]), removed, kept))
        filtering.append(dict(id=case["id"], has_removable_step=int(scores[-1][0]), step_removed=int(removed), rest_kept=int(kept)))
    scores = np.array(scores, dtype=int)
    for name, mask in (("all", np.ones(len(scores), bool)), ("has_removable_step", scores[:, 0] == 1), ("step_is_cause", scores[:, 0] == 0)):
        counts = scores[mask].sum(axis=0)
        filtering.append(dict(id=f"{name} ({int(mask.sum())} cases)", has_removable_step=int(counts[0]), step_removed=int(counts[1]), rest_kept=int(counts[2])))
    before_after, contrasts = fixes(scenes, trials, groups, draws)
    return {"recovery": recovery, "behaviour": behaviours, "filter": filtering, "before_after": before_after, "contrasts": contrasts}


def per_scene(trials, scenes, model, variant, fn):
    """Mean of fn over the runs of each scenario; NaN where the scenario has no runs of this variant."""
    out = []
    for s in scenes:
        runs = [trials.get((model, s["id"], variant, r)) for r in range(1, REPEATS + 1)]
        out.append(np.mean([fn(t) for t in runs]) if all(runs) else np.nan)
    return np.array(out)


def fixes(scenes, trials, groups, draws):
    """Before-and-after rows for the two problems, and paired differences in recovery between their texts."""
    recovered = lambda t: t["recovered"]
    measures = {"tool_calls": lambda t: t["behaviour"]["tool_calls"], "total_tokens": lambda t: t["total_tokens"],
                "ended_incomplete": lambda t: t["behaviour"]["ended_incomplete"]}
    before_after, contrasts = [], []
    for problem, failure, variants in BEFORE_AFTER:
        ids, index = groups[failure], draws[failure]
        for variant in variants:
            rates = {m: per_scene(trials, scenes, m, variant, recovered) for m in MODELS}
            rates[POOLED] = np.mean(list(rates.values()), axis=0)
            for model, data in rates.items():
                row = dict(problem=problem, failure_type=failure, variant=variant, model=model, **stat(data, ids, index))
                for name, fn in measures.items():
                    row[name] = float(np.mean([per_scene(trials, scenes, m, variant, fn)[ids].mean() for m in (MODELS if model == POOLED else (model,))]))
                before_after.append(row)
    pairs = (("expired_auth", [("C", "E2"), ("D2", "E2"), ("D2", "C"), ("C", "E2f")] + [(f, f[:-1]) for f in FILTERED]),
             ("quota_exhausted", [("D2", "D1")]))
    for failure, contrast in pairs:
        ids, index = groups[failure], draws[failure]
        for left, right in contrast:
            diff = {m: per_scene(trials, scenes, m, left, recovered) - per_scene(trials, scenes, m, right, recovered) for m in MODELS}
            diff[POOLED] = np.mean(list(diff.values()), axis=0)
            for model, data in diff.items():
                contrasts.append(dict(failure_type=failure, contrast=f"{left}-{right}", model=model, **stat(data, ids, index)))
    return before_after, contrasts


def print_tables(recovery, behaviour):
    rate = {(r["model"], r["failure_type"], r["condition"]): 100 * r["estimate"] for r in recovery if r["condition"]}
    percent = lambda x: f"{math.floor(x + 0.5):d}"
    columns = ("A", "C", "D1", "D2", "E1", "E2")
    header = "| Generic | Cause | Correct step, phrasing 1 | Correct step, phrasing 2 | Executable incorrect step | Unavailable incorrect step |"
    print("Table 6: recovery (%) by failure type, mean over the five models\n")
    print("| Failure type " + header + "\n|---|---:|---:|---:|---:|---:|---:|")
    for failure in FAILURES:
        print(f"| {failure} | " + " | ".join(percent(np.mean([rate[(m, failure, c)] for m in MODELS])) for c in columns) + " |")
    ended = {r["model"]: 100 * r["estimate"] for r in behaviour if r["failure_type"] == "expired_auth" and r["variant"] == "E2" and r["measure"] == "ended_incomplete"}
    print("\nRecovery (%) on the 24 expired-credential scenarios by model, and the share (%) of trials under the unavailable step that ended without a repair\n")
    print("| Model " + header + " Ended without repair |\n|---|---:|---:|---:|---:|---:|---:|---:|")
    for model in MODELS:
        print(f"| {model} | " + " | ".join(percent(rate[(model, "expired_auth", c)]) for c in columns) + f" | {percent(ended[model])} |")
    loss = {(r["model"], r["failure_type"]): r for r in recovery if r["contrast"] == "E2-C"}
    points = lambda r: f"{-100 * r['estimate']:.1f} [{-100 * r['ci_high']:.1f}, {-100 * r['ci_low']:.1f}]"
    print("\nRecovery lost to the unavailable step (cause minus unavailable step, points) with 95% intervals, on the failures the agent cannot see\n")
    print("| Model | " + " | ".join(INVISIBLE) + " |\n|---|---:|---:|---:|")
    for model in MODELS:
        print(f"| {model} | " + " | ".join(points(loss[(model, f)]) for f in INVISIBLE) + " |")
    diff = next(r for r in recovery if r["model"] == "gpt-6-astra minus gpt-5.5")
    print(f"\nExpired credentials, loss for gpt-6-astra minus loss for gpt-5.5 (points): {100 * diff['estimate']:.1f} [{100 * diff['ci_low']:.1f}, {100 * diff['ci_high']:.1f}]")
    gain = [r for r in recovery if r["contrast"] == "D-C" and r["failure_type"] == "invisible"]
    print("\nCorrect step minus cause (points) on the " + str(gain[0]["n_scenarios"]) + " scenarios of these three types, with 95% intervals\n")
    for r in gain:
        print(f"| {r['model']} | {100 * r['estimate']:+.1f} [{100 * r['ci_low']:+.1f}, {100 * r['ci_high']:+.1f}] |")


def print_fixes(before_after, contrasts):
    ci = lambda r: f"{100 * r['estimate']:.1f} [{100 * r['ci_low']:.1f}, {100 * r['ci_high']:.1f}]"
    for problem, failure, _ in BEFORE_AFTER:
        print(f"\nProblem {problem} ({failure}): recovery (%) with 95% interval, tool calls, tokens and share (%) ended without repair per trial\n")
        print("| Text | Model | Recovery | Tool calls | Tokens | Ended without repair |\n|---|---|---:|---:|---:|---:|")
        for r in before_after:
            if r["problem"] == problem:
                print(f"| {r['variant']} | {r['model']} | {ci(r)} | {r['tool_calls']:.2f} | {r['total_tokens']:.0f} | {100 * r['ended_incomplete']:.1f} |")
    print("\nDifferences in recovery (points) between texts, with 95% intervals; the suffix f marks a filtered text\n")
    print("| Failure type | Contrast | Model | Difference |\n|---|---|---|---:|")
    for r in contrasts:
        print(f"| {r['failure_type']} | {r['contrast']} | {r['model']} | {ci(r)} |")


def main():
    scenes = jsonl(ROOT / "experiment/scenarios/scenarios.jsonl")
    filters = jsonl(ROOT / "experiment/scenarios/filter_cases.jsonl")
    runs = ROOT / "experiment/runs"
    trials = {(model, r["scenario_id"], r["variant"], r["repeat"]): r for model in MODELS
              for name in (model, f"filtered-{model}") for r in jsonl(runs / f"{name}.jsonl")}
    outputs = {r["id"]: r["output_text"] for r in jsonl(runs / f"filter-{FILTER_MODEL}.jsonl")}
    tables = analyze(scenes, filters, trials, outputs)
    out = ROOT / "experiment/results"
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        write_csv(out / f"{name}.csv", rows)
    print_tables(tables["recovery"], tables["behaviour"])
    print_fixes(tables["before_after"], tables["contrasts"])
    cause = {s["id"]: s["error_texts"]["C"] for s in scenes}
    filtered = jsonl(runs / f"filter-expired-{FILTER_MODEL}.jsonl")
    same = sum(r["output_text"].strip() == cause[r["id"].split(":")[0]] for r in filtered)
    print(f"\nFiltered texts identical to the cause statement: {same} of {len(filtered)}")


if __name__ == "__main__":
    main()
