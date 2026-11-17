# Evaluation and reproducibility

Kivi is a **deterministic phonetic-memory system**, not an LLM. Its correction
policy uses explicit observations, context-sensitive lookup, confidence and
ambiguity checks, and explainable token decisions.

## Two independent checks

| Layer | Command | What it checks | Pass condition |
| --- | --- | --- | --- |
| Unit tests | `python -m pytest tests/ -q` | Core memory behavior, thresholds, ambiguity, context, casing, and reset; also validates the scenario contract | All pytest tests exit successfully |
| Scenario evaluation | `python eval/run_eval.py` | End-to-end expected text, intervention/no-intervention classification, and selected decision trace labels | Every check passes; the runner exits 0 |

**CI:** [GitHub Actions – Tests and evaluation](../.github/workflows/ci.yml)
runs both commands on Python 3.11 and 3.12 for pushes to `main`, pull
requests, and manual dispatches. Each run publishes its evaluation report and
JSON results as downloadable GitHub Actions artifacts.

## Reproduce locally

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -q
python eval/run_eval.py
```

No server, Docker service, database server, API key, LLM, or network call is
required **during evaluation**. Dependencies must be installed first.
The evaluator uses a separate SQLite database at `data/eval.db` and writes:

- [`results.json`](results.json): per-case expected/actual text, detailed
  reasoning traces, memory state, outcomes, and measured latency
- [`report.md`](report.md): human-readable summary and case-by-case results
- [`cases.json`](cases.json): scenario inputs and expected behavior
- [`run_eval.py`](run_eval.py): evaluation runner and reporting logic

The committed report is a **snapshot from a previous run**, not a live
build status. For fresh evidence, use the latest passing Actions run and its
attached artifacts. Timing values vary across machines and runs.

## What the metrics mean

- **Useful intervention:** a change was expected and the output is correct.
- **Correct non-intervention:** no change was expected and the output is correct.
- **Missed intervention:** a change was expected but absent or incorrect.
- **Incorrect intervention:** an unwanted change was made.
- **Wrong decision reason:** output text is right, but an explicitly checked
  token decision is wrong.
- **Precision and recall:** based on whether an intervention should occur,
  not on word-error rate or general speech-recognition quality.

The evaluator reports the count of checks and the split of these outcomes.
The existing snapshot contains **11 scenarios and 14 checks (14 passed)**,
including ambiguity and safe non-intervention cases. These are small,
hand-authored behavioral checks, not a statistical benchmark over a
representative real-world dataset. They do **not** establish production
accuracy, robustness against adversarial input, or generalization to
multilingual speech.

## CI safety and scope

CI uses read-only repository permissions and does not commit generated output.
It is a validation workflow: it does not deploy the app or expose secrets.
For substantial behavior changes, add or revise cases first, then ensure both
suites remain green.
