"""Validate the evaluation fixture and documented output contract.

These tests do not replace the end-to-end evaluation run in CI.
"""
import json
from pathlib import Path

CASES = Path(__file__).resolve().parent.parent / "eval" / "cases.json"


def test_evaluation_cases_are_well_formed():
    scenarios = json.loads(CASES.read_text(encoding="utf-8"))
    assert isinstance(scenarios, list) and scenarios, "No evaluation scenarios defined"

    scenario_ids = set()
    total_checks = 0
    for scenario in scenarios:
        assert isinstance(scenario.get("id"), str) and scenario["id"]
        assert scenario["id"] not in scenario_ids, "Duplicate scenario id"
        scenario_ids.add(scenario["id"])
        assert isinstance(scenario.get("checks"), list) and scenario["checks"]

        check_ids = set()
        for check in scenario["checks"]:
            total_checks += 1
            assert isinstance(check.get("id"), str) and check["id"]
            assert check["id"] not in check_ids, "Duplicate check id within scenario"
            check_ids.add(check["id"])
            assert isinstance(check.get("formatted_text"), str)
            assert isinstance(check.get("expected_output"), str)
            assert type(check.get("expect_intervention")) is bool
            for token, decision in check.get("expect_decisions", {}).items():
                assert isinstance(token, str) and token
                assert isinstance(decision, str) and decision

    assert total_checks > 0


def test_evaluation_contains_positive_and_negative_cases():
    scenarios = json.loads(CASES.read_text(encoding="utf-8"))
    labels = [check["expect_intervention"] for s in scenarios for check in s["checks"]]
    assert any(labels), "Evaluation must exercise expected interventions"
    assert not all(labels), "Evaluation must exercise expected non-interventions"
