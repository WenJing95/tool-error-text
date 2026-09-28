# MCP Error Messages Written for Developers Hurt the Most Capable Agents Most

Data and code for the paper.

- `survey/`: the 150 MCP servers (`servers.csv`), the 3,001 annotated failure paths (`error_messages.csv`), the annotation rules (`codebook.md`), the written instructions given to the annotating agents (`annotation_instructions.md`) and the script that prints Table 1, the counts of credential, permission and rate-limit failures and what their caller-dependent steps require (column `step_requires`) (`make_tables.py`).
- `experiment/scenarios/`: the 168 scenarios with their six error texts, tool lists, conversation prefixes and saved environment states (`scenarios.jsonl`), and the 949 error messages of the filtering test (`filter_cases.jsonl`).
- `experiment/runs/`: one record per trial for each of the five models (tool calls, final reply, recovery, behaviour codes, tokens), the 949 filtering outputs of gpt-6-luna on the survey messages (`filter-gpt-6-luna.jsonl`), its 96 filtered texts of the expired-credential scenarios (`filter-expired-gpt-6-luna.jsonl`, variants D1f, D2f, E1f and E2f), and the trials on those texts (`filtered-<model>.jsonl`).
- `experiment/results/`: recovery rates and contrasts (`recovery.csv`) and behaviour rates (`behaviour.csv`), recovery, tool calls, tokens and the share of trials ended without a repair under the original and the rewritten step (`before_after.csv`) and the differences between those texts, filtered texts included (`contrasts.csv`), each with 95% intervals from the scenario bootstrap, and the per-case filtering results (`filter.csv`).
- `experiment/code/`: the runner (`run.py`), the environment and recovery check on the BFCL runtime (`environment.py`, `bfcl_runtime/`), the behaviour judge (`behaviour.py`), the analysis that writes the result files and prints Tables 4 to 6 (`analyze.py`) and the script that draws Figure 1 (`plot_figures.py`).
- `figures/`: Figure 1 (`fig1_recovery.pdf`).

Recompute the tables and the figure from this directory (Python 3, NumPy, Matplotlib):

```sh
python survey/make_tables.py
python experiment/code/analyze.py
python experiment/code/plot_figures.py
```

Rerun the experiment with `OPENAI_API_KEY` set (this appends to `experiment/runs/`; move the released runs aside first):

```sh
python experiment/code/run.py --mode recovery
python experiment/code/run.py --mode filter
```

License: code MIT, annotation data CC BY 4.0, quoted error text as in its source repository, BFCL-derived content Apache 2.0 (see `LICENSE`).
