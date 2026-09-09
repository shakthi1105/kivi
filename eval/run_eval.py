"""Runs eval/cases.json against the memory system and writes:
  eval/results.json  -- full machine-readable detail per case (for inspection)
  eval/report.md      -- human-readable summary

Usage:
    python3 eval/run_eval.py

Each check in a scenario is classified into exactly one outcome:
  useful_intervention        -- expected an intervention, got the right one
  correct_non_intervention   -- expected no change, got no change
  missed_intervention        -- expected an intervention, system did nothing / wrong output   [FAIL]
  incorrect_intervention     -- expected no change, system changed the text anyway            [FAIL]
  wrong_decision_reason      -- output text matched but a specifically-checked token decision
                                 didn't match what was expected (e.g. already_correct vs no_memory) [FAIL]

This directly gives the precision/recall split the brief asks for: useful vs.
unnecessary/incorrect interventions are counted separately, not blended into
one pass rate.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.memory import MemoryStore  # noqa: E402
from app import db as db_module     # noqa: E402

EVAL_DB_PATH = str(ROOT / "data" / "eval.db")
CASES_PATH = Path(__file__).resolve().parent / "cases.json"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"
REPORT_PATH = Path(__file__).resolve().parent / "report.md"


def run():
    with open(CASES_PATH) as f:
        scenarios = json.load(f)

    store = MemoryStore(db_path=EVAL_DB_PATH)
    all_results = []
    latencies_ms = []

    for scenario in scenarios:
        if scenario.get("reset_before"):
            store.reset()
        for obs in scenario.get("setup_observations", []):
            store.add_observation(**obs)

        for check in scenario["checks"]:
            if check.get("reset_before_this_check"):
                store.reset()
            for obs in check.get("additional_observations", []):
                store.add_observation(**obs)

            t0 = time.perf_counter()
            result = store.resolve(check["formatted_text"], check.get("asr_text"))
            elapsed_ms = (time.perf_counter() - t0) * 1000
            latencies_ms.append(elapsed_ms)

            actual_output = result["memory_aware_text"]
            actual_intervened = any(t["decision"] == "intervened" for t in result["trace"])
            expected_output = check["expected_output"]
            expected_intervention = check["expect_intervention"]

            output_correct = actual_output == expected_output

            decision_checks_ok = True
            decision_check_detail = {}
            for token, expected_decision in check.get("expect_decisions", {}).items():
                matches = [t for t in result["trace"] if t["token"] == token]
                actual_decision = matches[0]["decision"] if matches else None
                decision_check_detail[token] = {"expected": expected_decision, "actual": actual_decision}
                if actual_decision != expected_decision:
                    decision_checks_ok = False

            if expected_intervention and actual_intervened and output_correct:
                outcome = "useful_intervention"
            elif not expected_intervention and not actual_intervened and output_correct:
                outcome = "correct_non_intervention"
            elif expected_intervention and (not actual_intervened or not output_correct):
                outcome = "missed_intervention"
            elif not expected_intervention and actual_intervened:
                outcome = "incorrect_intervention"
            else:
                outcome = "unexpected"

            if outcome in ("useful_intervention", "correct_non_intervention") and not decision_checks_ok:
                outcome = "wrong_decision_reason"

            passed = outcome in ("useful_intervention", "correct_non_intervention")

            all_results.append({
                "scenario_id": scenario["id"],
                "scenario_description": scenario["description"],
                "check_id": check["id"],
                "notes": check.get("notes", ""),
                "inputs": {
                    "asr_text": check.get("asr_text"),
                    "formatted_text": check["formatted_text"],
                },
                "expected_output": expected_output,
                "actual_output": actual_output,
                "expected_intervention": expected_intervention,
                "actual_intervened": actual_intervened,
                "outcome": outcome,
                "passed": passed,
                "decision_checks": decision_check_detail,
                "relevant_memory_state": store.memory_state(),
                "reasoning_trace": result["trace"],
                "latency_ms": round(elapsed_ms, 3),
            })

    # ---- aggregate stats -------------------------------------------------
    total = len(all_results)
    passed_n = sum(1 for r in all_results if r["passed"])
    useful = sum(1 for r in all_results if r["outcome"] == "useful_intervention")
    correct_noop = sum(1 for r in all_results if r["outcome"] == "correct_non_intervention")
    missed = [r for r in all_results if r["outcome"] == "missed_intervention"]
    incorrect = [r for r in all_results if r["outcome"] == "incorrect_intervention"]
    wrong_reason = [r for r in all_results if r["outcome"] == "wrong_decision_reason"]

    expected_pos = sum(1 for r in all_results if r["expected_intervention"])
    expected_neg = total - expected_pos
    true_pos = useful
    false_neg = len(missed)
    false_pos = len(incorrect)
    true_neg = correct_noop
    precision = true_pos / (true_pos + false_pos) if (true_pos + false_pos) else float("nan")
    recall = true_pos / (true_pos + false_neg) if (true_pos + false_neg) else float("nan")

    conn = db_module.get_connection(EVAL_DB_PATH)
    n_observations = conn.execute("SELECT COUNT(*) c FROM observations").fetchone()["c"]
    n_memory_entries = conn.execute("SELECT COUNT(*) c FROM memory_entries").fetchone()["c"]
    conn.close()

    summary = {
        "total_checks": total,
        "passed": passed_n,
        "failed": total - passed_n,
        "useful_interventions": useful,
        "correct_non_interventions": correct_noop,
        "missed_interventions": len(missed),
        "incorrect_interventions": len(incorrect),
        "wrong_decision_reason": len(wrong_reason),
        "precision": None if precision != precision else round(precision, 3),
        "recall": None if recall != recall else round(recall, 3),
        "expected_positive_cases": expected_pos,
        "expected_negative_cases": expected_neg,
        "avg_latency_ms": round(sum(latencies_ms) / len(latencies_ms), 3) if latencies_ms else 0,
        "max_latency_ms": round(max(latencies_ms), 3) if latencies_ms else 0,
        "model_usage": "none -- deterministic phonetic matching, no LLM calls in the resolve path",
        "estimated_cost_usd": 0.0,
        "final_observations_row_count": n_observations,
        "final_memory_entries_row_count": n_memory_entries,
    }

    with open(RESULTS_PATH, "w") as f:
        json.dump({"summary": summary, "cases": all_results}, f, indent=2)

    write_report(summary, all_results)

    print(json.dumps(summary, indent=2))
    return summary["failed"] == 0


def write_report(summary, results):
    lines = []
    lines.append("# Kivi Word Memory -- Evaluation Report\n")
    lines.append(f"**{summary['passed']}/{summary['total_checks']} checks passed.**\n")
    lines.append("## Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    for k, v in summary.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("Precision/recall are computed over the binary question *\"should the system have "
                  "intervened on this input?\"* -- a true positive is a correct, useful rewrite; a false "
                  "positive is an incorrect/unnecessary rewrite (the failure mode that erodes trust "
                  "fastest); a false negative is a missed correction the system had evidence for.\n")

    lines.append("## Per-case results\n")
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        lines.append(f"### [{mark}] {r['scenario_id']} / {r['check_id']}")
        lines.append(f"_{r['scenario_description']}_\n")
        lines.append(f"- Notes: {r['notes']}")
        lines.append(f"- Formatted input: `{r['inputs']['formatted_text']}`")
        lines.append(f"- Expected output: `{r['expected_output']}`")
        lines.append(f"- Actual output: `{r['actual_output']}`")
        lines.append(f"- Outcome: **{r['outcome']}**")
        lines.append(f"- Latency: {r['latency_ms']} ms")
        interesting = [t for t in r["reasoning_trace"] if t["decision"] != "no_memory"]
        if interesting:
            lines.append("- Token decisions:")
            for t in interesting:
                lines.append(f"  - `{t['token']}` -> **{t['decision']}** ({t['reason']})")
        lines.append("")

    REPORT_PATH.write_text("\n".join(lines))


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
