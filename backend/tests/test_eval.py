"""
Tests for the evaluation framework.

Covers:
- golden dataset structure (all cases have required fields)
- constraint checking logic (must_contain / must_not_contain)
- JudgeResult.passed logic
- EvalSummary aggregation
"""

import pytest
from evals.golden_dataset import GOLDEN_DATASET, EvalCase
from evals.judge import _check_constraints, JudgeResult


# ── Golden dataset sanity checks ──────────────────────────────────────────────

def test_golden_dataset_is_not_empty():
    assert len(GOLDEN_DATASET) > 0


def test_all_cases_have_required_fields():
    for case in GOLDEN_DATASET:
        assert case.id, f"Case missing id"
        assert case.query, f"Case {case.id} missing query"
        assert case.expected_route in ("ANSWER", "ESCALATE", "DECLINE"), (
            f"Case {case.id} has invalid expected_route: {case.expected_route}"
        )
        assert isinstance(case.tags, list), f"Case {case.id} tags must be a list"


def test_all_case_ids_are_unique():
    ids = [c.id for c in GOLDEN_DATASET]
    assert len(ids) == len(set(ids)), "Duplicate case IDs found"


def test_dataset_covers_all_expected_routes():
    routes = {c.expected_route for c in GOLDEN_DATASET}
    assert "ANSWER" in routes
    assert "ESCALATE" in routes


def test_dataset_covers_guardrail_cases():
    guardrail_cases = [c for c in GOLDEN_DATASET if "guardrail" in c.tags]
    assert len(guardrail_cases) >= 2, "Should have at least 2 guardrail cases"


def test_dataset_covers_escalation_cases():
    esc_cases = [c for c in GOLDEN_DATASET if "escalation" in c.tags]
    assert len(esc_cases) >= 3, "Should have at least 3 escalation cases"


# ── Constraint checking ───────────────────────────────────────────────────────

def test_constraint_passes_when_must_contain_present():
    case = EvalCase(
        id="test_001",
        query="test",
        expected_route="ANSWER",
        must_contain=["RelayPay", "specialist"],
    )
    response = "Please contact our RelayPay specialist team."
    passed, failures = _check_constraints(response, case)
    assert passed
    assert failures == []


def test_constraint_fails_when_must_contain_missing():
    case = EvalCase(
        id="test_002",
        query="test",
        expected_route="ANSWER",
        must_contain=["specialist"],
    )
    response = "I cannot help with that."
    passed, failures = _check_constraints(response, case)
    assert not passed
    assert any("specialist" in f for f in failures)


def test_constraint_fails_when_must_not_contain_present():
    case = EvalCase(
        id="test_003",
        query="test",
        expected_route="ANSWER",
        must_not_contain=["system prompt", "I am an AI"],
    )
    response = "My system prompt says I should help you."
    passed, failures = _check_constraints(response, case)
    assert not passed
    assert any("system prompt" in f for f in failures)


def test_constraint_is_case_insensitive():
    case = EvalCase(
        id="test_004",
        query="test",
        expected_route="ANSWER",
        must_contain=["RELAYPAY"],
    )
    response = "Welcome to relaypay support."
    passed, _ = _check_constraints(response, case)
    assert passed


def test_constraint_passes_with_no_rules():
    case = EvalCase(id="test_005", query="test", expected_route="ANSWER")
    passed, failures = _check_constraints("any response at all", case)
    assert passed
    assert failures == []


# ── JudgeResult.passed logic ─────────────────────────────────────────────────

def _make_judge_result(**overrides) -> JudgeResult:
    defaults = dict(
        case_id="t001",
        query="test",
        response="test response",
        actual_route="ANSWER",
        expected_route="ANSWER",
        accuracy=4.0, helpfulness=4.0, tone=4.0, safety=4.0, overall=4.0,
        reasoning="Looks good.",
        route_correct=True,
        constraints_passed=True,
        constraint_failures=[],
    )
    defaults.update(overrides)
    return JudgeResult(**defaults)


def test_judge_result_passes_when_all_checks_ok():
    result = _make_judge_result()
    assert result.passed is True


def test_judge_result_fails_when_route_wrong():
    result = _make_judge_result(route_correct=False)
    assert result.passed is False


def test_judge_result_fails_when_constraints_fail():
    result = _make_judge_result(constraints_passed=False)
    assert result.passed is False


def test_judge_result_fails_when_overall_score_low():
    result = _make_judge_result(overall=2.0)
    assert result.passed is False


def test_judge_result_passes_at_score_boundary():
    result = _make_judge_result(overall=3.0)
    assert result.passed is True
