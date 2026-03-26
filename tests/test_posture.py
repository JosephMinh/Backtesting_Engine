"""Contract tests for mission and live-lane posture constraints.

Verifies that the approved deployment posture (Plan v3.8 section 1.2) is
encoded as machine-readable policy assertions and that boundary enforcement
emits structured log output with stable reason codes.

Coverage required by bead backtesting_engine-ltc.1.1:
  - six core program questions remain explicit design drivers
  - MGC / 1OZ / IBKR / $5k / one-contract / one-host posture is unambiguous
  - live-eligible strategies limited to approved lower-frequency lane
  - valid-posture and violation scenarios with structured reason codes
"""

from __future__ import annotations

import json

import pytest

from shared.policy.posture import (
    APPROVED_POSTURE,
    CORE_PROGRAM_QUESTIONS,
    PostureCheckResult,
    PostureConstraints,
    check_account_value,
    check_active_bundles,
    check_broker,
    check_decision_interval,
    check_deployment_hosts,
    check_execution_symbol,
    check_live_contracts,
    check_research_symbol,
    validate_full_posture,
)


# ---------------------------------------------------------------------------
# Core program questions
# ---------------------------------------------------------------------------


class TestCoreProgramQuestions:
    """Verify the six core questions remain explicit design drivers."""

    def test_exactly_six_questions(self):
        assert len(CORE_PROGRAM_QUESTIONS) == 6

    def test_questions_are_nonempty_strings(self):
        for q in CORE_PROGRAM_QUESTIONS:
            assert isinstance(q, str)
            assert len(q) > 10

    def test_question_1_budget(self):
        assert "budget" in CORE_PROGRAM_QUESTIONS[0].lower()

    def test_question_2_parameter_regions(self):
        assert "parameter" in CORE_PROGRAM_QUESTIONS[1].lower()

    def test_question_3_realistic_fills(self):
        assert "realistic" in CORE_PROGRAM_QUESTIONS[2].lower()

    def test_question_4_portability(self):
        q = CORE_PROGRAM_QUESTIONS[3].lower()
        assert "mgc" in q and "1oz" in q.replace("1oz", "1oz")

    def test_question_5_replay(self):
        assert "replay" in CORE_PROGRAM_QUESTIONS[4].lower()

    def test_question_6_operational_risk(self):
        assert "operational" in CORE_PROGRAM_QUESTIONS[5].lower()


# ---------------------------------------------------------------------------
# Approved posture is unambiguous
# ---------------------------------------------------------------------------


class TestApprovedPosture:
    """Verify the posture defaults match Plan v3.8 section 1.2."""

    def test_research_symbol_is_mgc(self):
        assert APPROVED_POSTURE.research_symbol == "MGC"

    def test_execution_symbol_is_1oz(self):
        assert APPROVED_POSTURE.execution_symbol == "1OZ"

    def test_broker_is_ibkr(self):
        assert APPROVED_POSTURE.broker == "IBKR"

    def test_max_account_value_is_5000(self):
        assert APPROVED_POSTURE.max_account_value_usd == 5_000

    def test_max_live_contracts_is_1(self):
        assert APPROVED_POSTURE.max_live_contracts == 1

    def test_min_decision_interval_is_60s(self):
        assert APPROVED_POSTURE.min_decision_interval_seconds == 60

    def test_max_active_bundles_is_1(self):
        assert APPROVED_POSTURE.max_active_bundles_per_account == 1

    def test_max_deployment_hosts_is_1(self):
        assert APPROVED_POSTURE.max_deployment_hosts == 1

    def test_overnight_allowed_with_stricter_gates(self):
        assert APPROVED_POSTURE.overnight_holding_allowed is True
        assert APPROVED_POSTURE.overnight_requires_stricter_gates is True

    def test_posture_is_frozen(self):
        with pytest.raises(AttributeError):
            APPROVED_POSTURE.max_live_contracts = 5  # type: ignore[misc]

    def test_posture_serializes(self):
        d = APPROVED_POSTURE.to_dict()
        assert d["research_symbol"] == "MGC"
        assert d["execution_symbol"] == "1OZ"
        assert d["broker"] == "IBKR"
        assert d["max_account_value_usd"] == 5000


# ---------------------------------------------------------------------------
# Decision trace structure
# ---------------------------------------------------------------------------


class TestPostureTraceStructure:
    """Verify structured output from posture checks."""

    def test_trace_has_required_fields(self):
        result = check_research_symbol("MGC")
        d = result.to_dict()
        required = {"constraint", "passed", "reason_code", "actual", "expected", "diagnostic", "timestamp"}
        assert required.issubset(d.keys())

    def test_trace_serializes_to_json(self):
        result = check_broker("IBKR")
        parsed = json.loads(result.to_json())
        assert parsed["passed"] is True
        assert parsed["reason_code"] == "POSTURE_BROKER"

    def test_violated_property(self):
        passing = check_broker("IBKR")
        failing = check_broker("OTHER")
        assert not passing.violated
        assert failing.violated


# ---------------------------------------------------------------------------
# Symbol constraints
# ---------------------------------------------------------------------------


class TestResearchSymbol:
    """Verify research symbol constraint enforcement."""

    def test_pass_mgc(self):
        r = check_research_symbol("MGC")
        assert r.passed
        assert r.reason_code == "POSTURE_RESEARCH_SYMBOL"

    def test_violation_other_symbol(self):
        r = check_research_symbol("GC")
        assert r.violated
        assert r.actual == "GC"
        assert r.expected == "MGC"

    def test_trace_reason_code_stable(self):
        trace = json.loads(check_research_symbol("ES").to_json())
        assert trace["reason_code"] == "POSTURE_RESEARCH_SYMBOL"
        assert trace["passed"] is False


class TestExecutionSymbol:
    """Verify execution symbol constraint enforcement."""

    def test_pass_1oz(self):
        r = check_execution_symbol("1OZ")
        assert r.passed
        assert r.reason_code == "POSTURE_EXECUTION_SYMBOL"

    def test_violation_mgc(self):
        r = check_execution_symbol("MGC")
        assert r.violated


# ---------------------------------------------------------------------------
# Broker constraint
# ---------------------------------------------------------------------------


class TestBrokerConstraint:
    """Verify broker constraint enforcement."""

    def test_pass_ibkr(self):
        r = check_broker("IBKR")
        assert r.passed

    def test_violation_other_broker(self):
        r = check_broker("TRADIER")
        assert r.violated
        assert r.reason_code == "POSTURE_BROKER"


# ---------------------------------------------------------------------------
# Account size constraint
# ---------------------------------------------------------------------------


class TestAccountValue:
    """Verify account value boundary enforcement."""

    def test_pass_at_limit(self):
        r = check_account_value(5_000)
        assert r.passed

    def test_pass_below_limit(self):
        r = check_account_value(3_000)
        assert r.passed

    def test_violation_above_limit(self):
        r = check_account_value(10_000)
        assert r.violated
        assert r.actual == 10_000
        assert r.expected == 5_000

    def test_trace_includes_values(self):
        trace = json.loads(check_account_value(10_000).to_json())
        assert trace["actual"] == 10_000
        assert trace["expected"] == 5_000
        assert trace["reason_code"] == "POSTURE_ACCOUNT_VALUE"


# ---------------------------------------------------------------------------
# Live contracts constraint
# ---------------------------------------------------------------------------


class TestLiveContracts:
    """Verify live contract count boundary enforcement."""

    def test_pass_at_limit(self):
        assert check_live_contracts(1).passed

    def test_pass_zero(self):
        assert check_live_contracts(0).passed

    def test_violation_above_limit(self):
        r = check_live_contracts(2)
        assert r.violated
        assert r.reason_code == "POSTURE_LIVE_CONTRACTS"


# ---------------------------------------------------------------------------
# Decision interval (frequency lane) constraint
# ---------------------------------------------------------------------------


class TestDecisionInterval:
    """Verify lower-frequency lane enforcement.

    Live-eligible strategies must have decision intervals >= 60s.
    Sub-minute strategies are research-only.
    """

    def test_pass_at_60s(self):
        assert check_decision_interval(60).passed

    def test_pass_above_60s(self):
        assert check_decision_interval(300).passed

    def test_violation_sub_minute(self):
        r = check_decision_interval(30)
        assert r.violated
        assert "research-only" in r.diagnostic

    def test_violation_1s(self):
        r = check_decision_interval(1)
        assert r.violated
        assert r.reason_code == "POSTURE_DECISION_INTERVAL"


# ---------------------------------------------------------------------------
# Active bundles constraint
# ---------------------------------------------------------------------------


class TestActiveBundles:
    """Verify active bundle limit enforcement."""

    def test_pass_at_limit(self):
        assert check_active_bundles(1).passed

    def test_violation_above_limit(self):
        r = check_active_bundles(3)
        assert r.violated
        assert r.reason_code == "POSTURE_ACTIVE_BUNDLES"


# ---------------------------------------------------------------------------
# Deployment hosts constraint
# ---------------------------------------------------------------------------


class TestDeploymentHosts:
    """Verify single-host deployment constraint."""

    def test_pass_single_host(self):
        assert check_deployment_hosts(1).passed

    def test_violation_multi_host(self):
        r = check_deployment_hosts(2)
        assert r.violated
        assert r.reason_code == "POSTURE_DEPLOYMENT_HOSTS"


# ---------------------------------------------------------------------------
# Full posture validation
# ---------------------------------------------------------------------------


class TestFullPostureValidation:
    """Verify end-to-end posture validation."""

    def test_all_pass_with_approved_defaults(self):
        results = validate_full_posture()
        assert all(r.passed for r in results)
        assert len(results) == 8

    def test_single_violation_detected(self):
        results = validate_full_posture(live_contracts=5)
        violations = [r for r in results if r.violated]
        assert len(violations) == 1
        assert violations[0].constraint == "max_live_contracts"

    def test_multiple_violations_detected(self):
        results = validate_full_posture(
            research_symbol="ES",
            broker="TRADIER",
            account_value_usd=50_000,
            decision_interval_seconds=10,
        )
        violations = [r for r in results if r.violated]
        assert len(violations) == 4
        violated_constraints = {v.constraint for v in violations}
        assert violated_constraints == {
            "research_symbol",
            "broker",
            "max_account_value_usd",
            "min_decision_interval_seconds",
        }

    def test_all_results_have_stable_reason_codes(self):
        results = validate_full_posture()
        for r in results:
            assert r.reason_code.startswith("POSTURE_")

    def test_results_serialize_to_structured_log(self):
        results = validate_full_posture(execution_symbol="GC")
        for r in results:
            trace = json.loads(r.to_json())
            assert "constraint" in trace
            assert "passed" in trace
            assert "reason_code" in trace
            assert "diagnostic" in trace
