"""Draw Figure 1 (recovery by model and error text) from experiment/results/recovery.csv."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODELS = ("gpt-5.5", "gpt-5.6-sol", "gpt-6-sol", "gpt-6-astra", "gpt-6-luna")
LABELS = {"gpt-5.5": "GPT-5.5", "gpt-5.6-sol": "GPT-5.6 Sol", "gpt-6-sol": "GPT-6 Sol", "gpt-6-astra": "GPT-6 Astra", "gpt-6-luna": "GPT-6 Luna"}
CONDITIONS = (("A", "Generic"), ("C", "Cause"), ("D1", "Correct step 1"), ("D2", "Correct step 2"),
              ("E1", "Incorrect step, executable"), ("E2", "Incorrect step, unavailable"))


def main():
    with (ROOT / "experiment/results/recovery.csv").open(encoding="utf-8") as stream:
        rows = {(r["model"], r["condition"]): r for r in csv.DictReader(stream) if r["failure_type"] == "all" and r["condition"]}
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    width = 0.13
    x = np.arange(len(MODELS))
    for j, (condition, label) in enumerate(CONDITIONS):
        est = np.array([100 * float(rows[(m, condition)]["estimate"]) for m in MODELS])
        low = np.array([100 * float(rows[(m, condition)]["ci_low"]) for m in MODELS])
        high = np.array([100 * float(rows[(m, condition)]["ci_high"]) for m in MODELS])
        ax.bar(x + (j - 2.5) * width, est, width, yerr=[est - low, high - est], capsize=2, label=label, error_kw={"linewidth": 0.8})
    ax.set_xticks(x, [LABELS[m] for m in MODELS])
    ax.set_ylabel("Recovery (%)")
    ax.set_ylim(0, 100)
    ax.legend(ncol=3, fontsize=7, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    out = ROOT / "figures/fig1_recovery.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, metadata={"CreationDate": None, "ModDate": None})


if __name__ == "__main__":
    main()
