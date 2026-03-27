"""Selection hard gates that keep ranking secondary to explicit promotion policy."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.absolute_dollar_viability import (
    AbsoluteDollarDecision,
    AbsoluteDollarViabilityReport,
    AbsoluteDollarViabilityStatus,
)
from shared.policy.account_fit_gate import AccountFitExecutionDecision, AccountFitStatus
from shared.policy.discovery_accounting import (
    REQUIRED_NULL_MODEL_IDS,
    DiscoveryAccountingReport,
    DiscoveryAccountingStatus,
)
from shared.policy.evaluation_protocol import (
    EvaluationProtocolReport,
    EvaluationProtocolStatus,
)
from shared.policy.viability_gate import ExecutionSymbolCertificationReport, GateOutcome

SUPPORTED_SELECTION_HARD_GATES_SCHEMA_VERSION = 1

SELECTION_HARD_GATE_IDS = (
    "candidate_identity_alignment",
    "after_cost_profitability",
    "null_separation",
    "robustness_omission_lockbox",
    "portability_and_tradability",
    "account_fit",
    "absolute_dollar_viability_and_benchmarks",
    "execution_symbol_pin",
    "selection_artifact_bundle",
    "ranking_is_secondary",
)


def validate_selection_hard_gates_contract() -> list[str]:
    errors: list[str] = []
    if SUPPORTED_SELECTION_HARD_GATES_SCHEMA_VERSION < 1:
        errors.append("supported schema version must be positive")
    if len(SELECTION_HARD_GATE_IDS) != len(set(SELECTION_HARD_GATE_IDS)):
        errors.append("selection hard-gate identifiers must be unique")
    if REQUIRED_NULL_MODEL_IDS != (
        "random_entry",
        "time_shifted_anchor",
        "side_flipped_or_ablated",
        "permutation",
        "regime_conditional",
    ):
        errors.append("selection hard gates expect the canonical null-suite minimum")
    return errors


VALIDATION_ERRORS = validate_selection_hard_gates_contract()


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        decoded = decoder.decode(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON payload") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label}: expected JSON object")
    return decoded


def _sorted_unique(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@unique
class SelectionHardGatesStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


@unique
class SelectionHardGatesDecision(str, Enum):
    ADVANCE = "advance"
    HOLD = "hold"
    PIVOT = "pivot"
    REJECT = "reject"


@dataclass(frozen=True)
class AfterCostProfitabilityEvidence:
    evidence_id: str
    candidate_id: str
    family_id: str
    passed: bool
    net_profit_after_costs_usd: float
    retained_artifact_ids: tuple[str, ...]
    retained_log_ids: tuple[str, ...]
    operator_reason_bundle: tuple[str, ...]
    explanation: str

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AfterCostProfitabilityEvidence:
        return cls(
            evidence_id=str(payload["evidence_id"]),
            candidate_id=str(payload["candidate_id"]),
            family_id=str(payload["family_id"]),
            passed=bool(payload["passed"]),
            net_profit_after_costs_usd=float(payload["net_profit_after_costs_usd"]),
            retained_artifact_ids=tuple(
                str(item) for item in payload["retained_artifact_ids"]
            ),
            retained_log_ids=tuple(str(item) for item in payload["retained_log_ids"]),
            operator_reason_bundle=tuple(
                str(item) for item in payload["operator_reason_bundle"]
            ),
            explanation=str(payload["explanation"]),
        )


@dataclass(frozen=True)
class ParetoRankingView:
    ranking_view_id: str
    frontier_rank: int
    dominance_score: float
    tie_break_metrics: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ParetoRankingView:
        return cls(
            ranking_view_id=str(payload["ranking_view_id"]),
            frontier_rank=int(payload["frontier_rank"]),
            dominance_score=float(payload["dominance_score"]),
            tie_break_metrics=tuple(str(item) for item in payload["tie_break_metrics"]),
        )


@dataclass(frozen=True)
class SelectionArtifactBundle:
    artifact_manifest_id: str
    retained_log_ids: tuple[str, ...]
    correlation_ids: tuple[str, ...]
    expected_actual_diff_ids: tuple[str, ...]
    operator_reason_bundle: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SelectionArtifactBundle:
        return cls(
            artifact_manifest_id=str(payload["artifact_manifest_id"]),
            retained_log_ids=tuple(str(item) for item in payload["retained_log_ids"]),
            correlation_ids=tuple(str(item) for item in payload["correlation_ids"]),
            expected_actual_diff_ids=tuple(
                str(item) for item in payload["expected_actual_diff_ids"]
            ),
            operator_reason_bundle=tuple(
                str(item) for item in payload["operator_reason_bundle"]
            ),
        )


def _certification_from_dict(
    payload: dict[str, object],
) -> ExecutionSymbolCertificationReport:
    return ExecutionSymbolCertificationReport(
        research_symbol=str(payload["research_symbol"]),
        execution_symbol=str(payload["execution_symbol"]),
        finalist_id=str(payload["finalist_id"]),
        execution_symbol_viability_report_id=str(
            payload["execution_symbol_viability_report_id"]
        ),
        execution_symbol_viability_passed=bool(
            payload["execution_symbol_viability_passed"]
        ),
        portability_study_required=bool(payload["portability_study_required"]),
        portability_study_completed=bool(payload["portability_study_completed"]),
        portability_study_id=(
            None
            if payload.get("portability_study_id") in (None, "")
            else str(payload["portability_study_id"])
        ),
        portability_certified=bool(payload["portability_certified"]),
        portability_dimensions=[
            dict(item) for item in payload.get("portability_dimensions", [])
        ],
        portability_passed_count=int(payload["portability_passed_count"]),
        portability_failed_count=int(payload["portability_failed_count"]),
        sufficient_native_1oz_history_exists=bool(
            payload["sufficient_native_1oz_history_exists"]
        ),
        native_1oz_validation_required=bool(payload["native_1oz_validation_required"]),
        native_1oz_validation_completed=bool(payload["native_1oz_validation_completed"]),
        native_1oz_validation_study_id=(
            None
            if payload.get("native_1oz_validation_study_id") in (None, "")
            else str(payload["native_1oz_validation_study_id"])
        ),
        native_1oz_validation_passed=bool(payload["native_1oz_validation_passed"]),
        promotable_finalist_allowed=bool(payload["promotable_finalist_allowed"]),
        outcome_recommendation=str(payload["outcome_recommendation"]),
        rationale=str(payload["rationale"]),
        reason_code=str(payload["reason_code"]),
        timestamp=str(payload.get("timestamp", _utc_now())),
    )


@dataclass(frozen=True)
class SelectionHardGatesRequest:
    evaluation_id: str
    candidate_id: str
    family_id: str
    after_cost_profitability: AfterCostProfitabilityEvidence
    discovery_accounting_report: DiscoveryAccountingReport
    evaluation_protocol_report: EvaluationProtocolReport
    execution_symbol_certification: ExecutionSymbolCertificationReport
    account_fit_decision: AccountFitExecutionDecision
    absolute_dollar_viability_report: AbsoluteDollarViabilityReport
    selection_artifact_bundle: SelectionArtifactBundle
    selected_execution_symbol: str | None = None
    pareto_ranking: ParetoRankingView | None = None
    schema_version: int = SUPPORTED_SELECTION_HARD_GATES_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "candidate_id": self.candidate_id,
            "family_id": self.family_id,
            "after_cost_profitability": self.after_cost_profitability.to_dict(),
            "discovery_accounting_report": self.discovery_accounting_report.to_dict(),
            "evaluation_protocol_report": self.evaluation_protocol_report.to_dict(),
            "execution_symbol_certification": self.execution_symbol_certification.to_dict(),
            "account_fit_decision": self.account_fit_decision.to_dict(),
            "absolute_dollar_viability_report": self.absolute_dollar_viability_report.to_dict(),
            "selection_artifact_bundle": self.selection_artifact_bundle.to_dict(),
            "selected_execution_symbol": self.selected_execution_symbol,
            "pareto_ranking": (
                None if self.pareto_ranking is None else self.pareto_ranking.to_dict()
            ),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SelectionHardGatesRequest:
        pareto_payload = payload.get("pareto_ranking")
        return cls(
            evaluation_id=str(payload["evaluation_id"]),
            candidate_id=str(payload["candidate_id"]),
            family_id=str(payload["family_id"]),
            after_cost_profitability=AfterCostProfitabilityEvidence.from_dict(
                dict(payload["after_cost_profitability"])
            ),
            discovery_accounting_report=DiscoveryAccountingReport.from_dict(
                dict(payload["discovery_accounting_report"])
            ),
            evaluation_protocol_report=EvaluationProtocolReport.from_dict(
                dict(payload["evaluation_protocol_report"])
            ),
            execution_symbol_certification=_certification_from_dict(
                dict(payload["execution_symbol_certification"])
            ),
            account_fit_decision=AccountFitExecutionDecision.from_dict(
                dict(payload["account_fit_decision"])
            ),
            absolute_dollar_viability_report=AbsoluteDollarViabilityReport.from_dict(
                dict(payload["absolute_dollar_viability_report"])
            ),
            selection_artifact_bundle=SelectionArtifactBundle.from_dict(
                dict(payload["selection_artifact_bundle"])
            ),
            selected_execution_symbol=(
                None
                if payload.get("selected_execution_symbol") in (None, "")
                else str(payload["selected_execution_symbol"])
            ),
            pareto_ranking=(
                None
                if pareto_payload is None
                else ParetoRankingView.from_dict(dict(pareto_payload))
            ),
            schema_version=int(
                payload.get(
                    "schema_version", SUPPORTED_SELECTION_HARD_GATES_SCHEMA_VERSION
                )
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> SelectionHardGatesRequest:
        return cls.from_dict(
            _decode_json_object(payload, label="selection_hard_gates_request")
        )


@dataclass(frozen=True)
class SelectionHardGateCheckResult:
    gate_id: str
    passed: bool
    reason_code: str
    explanation: str
    evidence_surface: str
    evidence_ids: tuple[str, ...] = ()
    context: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "passed": self.passed,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "evidence_surface": self.evidence_surface,
            "evidence_ids": list(self.evidence_ids),
            "context": _jsonable(self.context),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SelectionHardGateCheckResult:
        return cls(
            gate_id=str(payload["gate_id"]),
            passed=bool(payload["passed"]),
            reason_code=str(payload["reason_code"]),
            explanation=str(payload["explanation"]),
            evidence_surface=str(payload["evidence_surface"]),
            evidence_ids=tuple(str(item) for item in payload["evidence_ids"]),
            context=dict(payload.get("context", {})),
        )


@dataclass(frozen=True)
class SelectionHardGatesReport:
    evaluation_id: str
    candidate_id: str
    family_id: str
    status: SelectionHardGatesStatus
    decision: SelectionHardGatesDecision
    reason_code: str
    selected_execution_symbol: str | None
    hard_gates_passed: bool
    secondary_ranking_considered: bool
    triggered_gate_ids: tuple[str, ...]
    retained_artifact_ids: tuple[str, ...]
    retained_log_ids: tuple[str, ...]
    correlation_ids: tuple[str, ...]
    expected_actual_diff_ids: tuple[str, ...]
    operator_reason_bundle: tuple[str, ...]
    pareto_frontier_rank: int | None
    pareto_dominance_score: float | None
    check_results: tuple[SelectionHardGateCheckResult, ...]
    explanation: str
    remediation: str
    evaluated_at_utc: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "candidate_id": self.candidate_id,
            "family_id": self.family_id,
            "status": self.status.value,
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "selected_execution_symbol": self.selected_execution_symbol,
            "hard_gates_passed": self.hard_gates_passed,
            "secondary_ranking_considered": self.secondary_ranking_considered,
            "triggered_gate_ids": list(self.triggered_gate_ids),
            "retained_artifact_ids": list(self.retained_artifact_ids),
            "retained_log_ids": list(self.retained_log_ids),
            "correlation_ids": list(self.correlation_ids),
            "expected_actual_diff_ids": list(self.expected_actual_diff_ids),
            "operator_reason_bundle": list(self.operator_reason_bundle),
            "pareto_frontier_rank": self.pareto_frontier_rank,
            "pareto_dominance_score": self.pareto_dominance_score,
            "check_results": [result.to_dict() for result in self.check_results],
            "explanation": self.explanation,
            "remediation": self.remediation,
            "evaluated_at_utc": self.evaluated_at_utc,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SelectionHardGatesReport:
        pareto_rank = payload.get("pareto_frontier_rank")
        pareto_score = payload.get("pareto_dominance_score")
        return cls(
            evaluation_id=str(payload["evaluation_id"]),
            candidate_id=str(payload["candidate_id"]),
            family_id=str(payload["family_id"]),
            status=SelectionHardGatesStatus(str(payload["status"])),
            decision=SelectionHardGatesDecision(str(payload["decision"])),
            reason_code=str(payload["reason_code"]),
            selected_execution_symbol=(
                None
                if payload.get("selected_execution_symbol") in (None, "")
                else str(payload["selected_execution_symbol"])
            ),
            hard_gates_passed=bool(payload["hard_gates_passed"]),
            secondary_ranking_considered=bool(payload["secondary_ranking_considered"]),
            triggered_gate_ids=tuple(str(item) for item in payload["triggered_gate_ids"]),
            retained_artifact_ids=tuple(
                str(item) for item in payload["retained_artifact_ids"]
            ),
            retained_log_ids=tuple(str(item) for item in payload["retained_log_ids"]),
            correlation_ids=tuple(str(item) for item in payload["correlation_ids"]),
            expected_actual_diff_ids=tuple(
                str(item) for item in payload["expected_actual_diff_ids"]
            ),
            operator_reason_bundle=tuple(
                str(item) for item in payload["operator_reason_bundle"]
            ),
            pareto_frontier_rank=(
                None if pareto_rank is None else int(pareto_rank)
            ),
            pareto_dominance_score=(
                None if pareto_score is None else float(pareto_score)
            ),
            check_results=tuple(
                SelectionHardGateCheckResult.from_dict(dict(item))
                for item in payload["check_results"]
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            evaluated_at_utc=str(payload["evaluated_at_utc"]),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> SelectionHardGatesReport:
        return cls.from_dict(
            _decode_json_object(payload, label="selection_hard_gates_report")
        )


def _check(
    gate_id: str,
    *,
    passed: bool,
    reason_code: str,
    explanation: str,
    evidence_surface: str,
    evidence_ids: tuple[str, ...] = (),
    context: dict[str, object] | None = None,
) -> SelectionHardGateCheckResult:
    return SelectionHardGateCheckResult(
        gate_id=gate_id,
        passed=passed,
        reason_code=reason_code,
        explanation=explanation,
        evidence_surface=evidence_surface,
        evidence_ids=evidence_ids,
        context={} if context is None else context,
    )


def _invalid_report(
    request: SelectionHardGatesRequest,
    *,
    reason_code: str,
    explanation: str,
) -> SelectionHardGatesReport:
    check = _check(
        SELECTION_HARD_GATE_IDS[0],
        passed=False,
        reason_code=reason_code,
        explanation=explanation,
        evidence_surface="selection_hard_gates",
        evidence_ids=(request.evaluation_id,),
    )
    return SelectionHardGatesReport(
        evaluation_id=request.evaluation_id,
        candidate_id=request.candidate_id,
        family_id=request.family_id,
        status=SelectionHardGatesStatus.INVALID,
        decision=SelectionHardGatesDecision.HOLD,
        reason_code=reason_code,
        selected_execution_symbol=None,
        hard_gates_passed=False,
        secondary_ranking_considered=request.pareto_ranking is not None,
        triggered_gate_ids=(check.gate_id,),
        retained_artifact_ids=(),
        retained_log_ids=(),
        correlation_ids=(),
        expected_actual_diff_ids=(),
        operator_reason_bundle=(),
        pareto_frontier_rank=(
            None if request.pareto_ranking is None else request.pareto_ranking.frontier_rank
        ),
        pareto_dominance_score=(
            None
            if request.pareto_ranking is None
            else request.pareto_ranking.dominance_score
        ),
        check_results=(check,),
        explanation=explanation,
        remediation="Repair the malformed selection payload before attempting advancement.",
    )


def _identity_check(
    request: SelectionHardGatesRequest,
) -> SelectionHardGateCheckResult:
    issues: list[str] = []
    if request.after_cost_profitability.candidate_id != request.candidate_id:
        issues.append("after_cost_profitability candidate mismatch")
    if request.after_cost_profitability.family_id != request.family_id:
        issues.append("after_cost_profitability family mismatch")
    if request.discovery_accounting_report.family_id != request.family_id:
        issues.append("discovery_accounting family mismatch")
    if request.absolute_dollar_viability_report.candidate_id != request.candidate_id:
        issues.append("absolute_dollar_viability candidate mismatch")
    if request.absolute_dollar_viability_report.strategy_family_id != request.family_id:
        issues.append("absolute_dollar_viability family mismatch")
    if request.account_fit_decision.candidate_id != request.candidate_id:
        issues.append("account_fit candidate mismatch")
    if request.execution_symbol_certification.finalist_id != request.candidate_id:
        issues.append("execution_symbol_certification candidate mismatch")

    passed = not issues
    return _check(
        SELECTION_HARD_GATE_IDS[0],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_IDENTITIES_ALIGNED"
            if passed
            else "SELECTION_HARD_GATES_IDENTITY_MISMATCH"
        ),
        explanation=(
            "Candidate and family identifiers align across the upstream gate reports."
            if passed
            else "All upstream gate reports must refer to the same candidate and family."
        ),
        evidence_surface="selection_hard_gates",
        evidence_ids=(
            request.after_cost_profitability.evidence_id,
            request.discovery_accounting_report.case_id,
            request.evaluation_protocol_report.case_id,
            request.execution_symbol_certification.finalist_id,
            request.account_fit_decision.candidate_id,
            request.absolute_dollar_viability_report.evaluation_id,
        ),
        context={"issues": issues},
    )


def _after_cost_profitability_check(
    request: SelectionHardGatesRequest,
) -> SelectionHardGateCheckResult:
    passed = (
        request.after_cost_profitability.passed
        and request.after_cost_profitability.net_profit_after_costs_usd > 0
        and bool(request.after_cost_profitability.retained_artifact_ids)
        and bool(request.after_cost_profitability.retained_log_ids)
        and bool(request.after_cost_profitability.operator_reason_bundle)
    )
    return _check(
        SELECTION_HARD_GATE_IDS[1],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_AFTER_COST_PROFITABLE"
            if passed
            else "SELECTION_HARD_GATES_AFTER_COST_PROFITABILITY_FAILED"
        ),
        explanation=(
            "After-cost profitability evidence is positive and retained for audit."
            if passed
            else "Advancement requires retained evidence that the candidate is profitable after realistic costs."
        ),
        evidence_surface="after_cost_profitability",
        evidence_ids=(
            request.after_cost_profitability.evidence_id,
            *request.after_cost_profitability.retained_artifact_ids,
        ),
        context={
            "net_profit_after_costs_usd": request.after_cost_profitability.net_profit_after_costs_usd,
            "retained_log_ids": list(request.after_cost_profitability.retained_log_ids),
        },
    )


def _null_separation_check(
    request: SelectionHardGatesRequest,
) -> SelectionHardGateCheckResult:
    required_nulls = set(REQUIRED_NULL_MODEL_IDS)
    completed_nulls = set(request.discovery_accounting_report.completed_null_model_ids)
    missing_nulls = tuple(sorted(required_nulls - completed_nulls))
    passed = (
        request.discovery_accounting_report.status == DiscoveryAccountingStatus.PASS.value
        and not missing_nulls
    )
    return _check(
        SELECTION_HARD_GATE_IDS[2],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_NULL_SEPARATION_PASSED"
            if passed
            else request.discovery_accounting_report.reason_code
        ),
        explanation=(
            "The candidate cleared the required null suite and discovery accounting controls."
            if passed
            else "Selection requires the full null suite and a passing discovery-accounting report before advancement."
        ),
        evidence_surface="discovery_accounting",
        evidence_ids=(
            request.discovery_accounting_report.case_id,
            *request.discovery_accounting_report.completed_null_model_ids,
        ),
        context={
            "status": request.discovery_accounting_report.status,
            "decision": request.discovery_accounting_report.decision,
            "missing_null_model_ids": list(missing_nulls),
            "triggered_check_ids": list(
                request.discovery_accounting_report.triggered_check_ids
            ),
        },
    )


def _evaluation_protocol_check(
    request: SelectionHardGatesRequest,
) -> SelectionHardGateCheckResult:
    report = request.evaluation_protocol_report
    passed = (
        report.status == EvaluationProtocolStatus.PASS.value
        and report.candidate_freeze_ready
    )
    return _check(
        SELECTION_HARD_GATE_IDS[3],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_EVALUATION_PROTOCOL_PASSED"
            if passed
            else report.reason_code
        ),
        explanation=(
            "Robustness, omission, power, and lockbox prerequisites are complete."
            if passed
            else "Selection cannot advance while robustness, omission, power, or lockbox protocol evidence remains incomplete."
        ),
        evidence_surface="evaluation_protocol",
        evidence_ids=(report.case_id, *report.retained_artifact_ids),
        context={
            "status": report.status,
            "decision": report.decision,
            "triggered_check_ids": list(report.triggered_check_ids),
            "candidate_freeze_ready": report.candidate_freeze_ready,
        },
    )


def _portability_tradability_check(
    request: SelectionHardGatesRequest,
) -> SelectionHardGateCheckResult:
    report = request.execution_symbol_certification
    evidence_ids = _sorted_unique(
        [
            report.execution_symbol_viability_report_id,
            report.portability_study_id or "",
            report.native_1oz_validation_study_id or "",
        ]
    )
    passed = report.promotable_finalist_allowed
    return _check(
        SELECTION_HARD_GATE_IDS[4],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_PORTABILITY_AND_TRADABILITY_PASSED"
            if passed
            else report.reason_code
        ),
        explanation=(
            "Execution-symbol tradability, portability, and native validation all permit advancement."
            if passed
            else "Selection requires a promotable execution-symbol certification result before advancement."
        ),
        evidence_surface="execution_symbol_certification",
        evidence_ids=evidence_ids,
        context={
            "execution_symbol": report.execution_symbol,
            "outcome_recommendation": report.outcome_recommendation,
            "portability_certified": report.portability_certified,
            "native_1oz_validation_required": report.native_1oz_validation_required,
            "native_1oz_validation_passed": report.native_1oz_validation_passed,
        },
    )


def _account_fit_check(
    request: SelectionHardGatesRequest,
) -> SelectionHardGateCheckResult:
    decision = request.account_fit_decision
    passed = decision.status == AccountFitStatus.PASS.value
    return _check(
        SELECTION_HARD_GATE_IDS[5],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_ACCOUNT_FIT_PASSED"
            if passed
            else decision.reason_code
        ),
        explanation=(
            "The actual execution contract is promotable under the account-fit decision."
            if passed
            else "Selection requires a passing account-fit execution decision on the actual execution contract."
        ),
        evidence_surface="account_fit",
        evidence_ids=decision.source_case_ids,
        context={
            "status": decision.status,
            "allowed_execution_symbols": list(decision.allowed_execution_symbols),
            "selected_execution_symbol": decision.selected_execution_symbol,
        },
    )


def _absolute_dollar_viability_check(
    request: SelectionHardGatesRequest,
) -> SelectionHardGateCheckResult:
    report = request.absolute_dollar_viability_report
    passed = (
        report.status == AbsoluteDollarViabilityStatus.PASS.value
        and report.decision == AbsoluteDollarDecision.KEEP.value
    )
    return _check(
        SELECTION_HARD_GATE_IDS[6],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_ABSOLUTE_DOLLAR_PASSED"
            if passed
            else report.reason_code
        ),
        explanation=(
            "Absolute-dollar viability and benchmark comparisons support advancement."
            if passed
            else "Selection requires a keep decision from the absolute-dollar viability and benchmark gate."
        ),
        evidence_surface="absolute_dollar_viability",
        evidence_ids=(report.evaluation_id, *report.source_ids),
        context={
            "status": report.status,
            "decision": report.decision,
            "failed_check_ids": list(report.failed_check_ids),
            "execution_symbol": report.execution_symbol,
        },
    )


def _selected_execution_symbol(
    request: SelectionHardGatesRequest,
) -> str | None:
    return (
        request.account_fit_decision.selected_execution_symbol
        or request.selected_execution_symbol
    )


def _execution_symbol_pin_check(
    request: SelectionHardGatesRequest,
) -> SelectionHardGateCheckResult:
    selected_symbol = _selected_execution_symbol(request)
    certification_symbol = request.execution_symbol_certification.execution_symbol
    viability_symbol = request.absolute_dollar_viability_report.execution_symbol
    allowed_symbols = request.account_fit_decision.allowed_execution_symbols
    passed = bool(
        selected_symbol
        and selected_symbol in allowed_symbols
        and selected_symbol == certification_symbol
        and selected_symbol == viability_symbol
    )
    return _check(
        SELECTION_HARD_GATE_IDS[7],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_EXECUTION_SYMBOL_PINNED"
            if passed
            else "SELECTION_HARD_GATES_EXECUTION_SYMBOL_PIN_REQUIRED"
        ),
        explanation=(
            "Selection is pinned to one actual execution symbol that matches every downstream gate."
            if passed
            else "Selection must pin one actual execution symbol that is allowed by account-fit and matches the certification and economics reports."
        ),
        evidence_surface="execution_symbol_binding",
        evidence_ids=(
            *request.account_fit_decision.source_case_ids,
            request.execution_symbol_certification.execution_symbol_viability_report_id,
            request.absolute_dollar_viability_report.evaluation_id,
        ),
        context={
            "selected_execution_symbol": selected_symbol,
            "allowed_execution_symbols": list(allowed_symbols),
            "certification_execution_symbol": certification_symbol,
            "economics_execution_symbol": viability_symbol,
        },
    )


def _selection_artifact_bundle_check(
    request: SelectionHardGatesRequest,
) -> SelectionHardGateCheckResult:
    bundle = request.selection_artifact_bundle
    passed = bool(
        bundle.artifact_manifest_id
        and bundle.retained_log_ids
        and bundle.correlation_ids
        and bundle.expected_actual_diff_ids
        and bundle.operator_reason_bundle
    )
    return _check(
        SELECTION_HARD_GATE_IDS[8],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_ARTIFACT_BUNDLE_COMPLETE"
            if passed
            else "SELECTION_HARD_GATES_ARTIFACT_BUNDLE_INCOMPLETE"
        ),
        explanation=(
            "Selection retains manifest, logs, correlations, diffs, and operator reasons."
            if passed
            else "Selection must retain structured logs, correlation IDs, expected-versus-actual diffs, artifact manifests, and operator-readable reasons."
        ),
        evidence_surface="selection_artifact_bundle",
        evidence_ids=(
            bundle.artifact_manifest_id,
            *bundle.retained_log_ids,
            *bundle.expected_actual_diff_ids,
        ),
        context={
            "correlation_ids": list(bundle.correlation_ids),
            "operator_reason_bundle": list(bundle.operator_reason_bundle),
        },
    )


def _ranking_secondary_check(
    *,
    request: SelectionHardGatesRequest,
    provisional_decision: SelectionHardGatesDecision,
    hard_gate_failures_present: bool,
) -> SelectionHardGateCheckResult:
    ranking_present = request.pareto_ranking is not None
    passed = not (
        ranking_present
        and hard_gate_failures_present
        and provisional_decision == SelectionHardGatesDecision.ADVANCE
    )
    return _check(
        SELECTION_HARD_GATE_IDS[9],
        passed=passed,
        reason_code=(
            "SELECTION_HARD_GATES_RANKING_REMAINS_SECONDARY"
            if passed
            else "SELECTION_HARD_GATES_RANKING_OVERRIDES_FORBIDDEN"
        ),
        explanation=(
            "Pareto or ranking views remain secondary to the hard pass-fail gates."
            if passed
            else "Ranking inputs must never override a failed hard gate."
        ),
        evidence_surface="selection_ranking",
        evidence_ids=()
        if request.pareto_ranking is None
        else (request.pareto_ranking.ranking_view_id,),
        context={
            "ranking_present": ranking_present,
            "provisional_decision": provisional_decision.value,
        },
    )


def _build_failure_decision(
    checks: tuple[SelectionHardGateCheckResult, ...],
) -> tuple[SelectionHardGatesDecision, str]:
    failures = {check.gate_id: check for check in checks if not check.passed}

    if not failures:
        return (
            SelectionHardGatesDecision.ADVANCE,
            "SELECTION_HARD_GATES_PASSED",
        )
    if SELECTION_HARD_GATE_IDS[6] in failures:
        check = failures[SELECTION_HARD_GATE_IDS[6]]
        if check.context.get("decision") == AbsoluteDollarDecision.PIVOT.value:
            return (SelectionHardGatesDecision.PIVOT, check.reason_code)
        return (SelectionHardGatesDecision.REJECT, check.reason_code)
    if SELECTION_HARD_GATE_IDS[4] in failures:
        check = failures[SELECTION_HARD_GATE_IDS[4]]
        if check.context.get("outcome_recommendation") == GateOutcome.PIVOT.value:
            return (SelectionHardGatesDecision.PIVOT, check.reason_code)
        if check.context.get("outcome_recommendation") == GateOutcome.NARROW.value:
            return (SelectionHardGatesDecision.HOLD, check.reason_code)
        return (SelectionHardGatesDecision.REJECT, check.reason_code)
    if SELECTION_HARD_GATE_IDS[5] in failures:
        return (
            SelectionHardGatesDecision.REJECT,
            failures[SELECTION_HARD_GATE_IDS[5]].reason_code,
        )
    if SELECTION_HARD_GATE_IDS[1] in failures:
        return (
            SelectionHardGatesDecision.REJECT,
            failures[SELECTION_HARD_GATE_IDS[1]].reason_code,
        )
    if SELECTION_HARD_GATE_IDS[2] in failures or SELECTION_HARD_GATE_IDS[3] in failures:
        gate_id = (
            SELECTION_HARD_GATE_IDS[2]
            if SELECTION_HARD_GATE_IDS[2] in failures
            else SELECTION_HARD_GATE_IDS[3]
        )
        return (SelectionHardGatesDecision.HOLD, failures[gate_id].reason_code)
    if SELECTION_HARD_GATE_IDS[7] in failures or SELECTION_HARD_GATE_IDS[8] in failures:
        gate_id = (
            SELECTION_HARD_GATE_IDS[7]
            if SELECTION_HARD_GATE_IDS[7] in failures
            else SELECTION_HARD_GATE_IDS[8]
        )
        return (SelectionHardGatesDecision.HOLD, failures[gate_id].reason_code)
    if SELECTION_HARD_GATE_IDS[0] in failures:
        return (SelectionHardGatesDecision.HOLD, failures[SELECTION_HARD_GATE_IDS[0]].reason_code)
    return (SelectionHardGatesDecision.HOLD, next(iter(failures.values())).reason_code)


def _build_explanation(
    report: SelectionHardGatesReport,
) -> str:
    if report.status == SelectionHardGatesStatus.PASS:
        if report.secondary_ranking_considered:
            return (
                "All explicit selection gates passed, the candidate is pinned to the actual execution symbol, "
                "and the Pareto view remained secondary to the gate outcome."
            )
        return (
            "All explicit selection gates passed and the candidate is pinned to the actual execution symbol."
        )

    failing_gate_ids = set(report.triggered_gate_ids)
    segments: list[str] = []
    if SELECTION_HARD_GATE_IDS[1] in failing_gate_ids:
        segments.append("After-cost profitability is not yet demonstrated.")
    if SELECTION_HARD_GATE_IDS[2] in failing_gate_ids:
        segments.append("Null separation or discovery accounting has not cleared.")
    if SELECTION_HARD_GATE_IDS[3] in failing_gate_ids:
        segments.append("Robustness, omission, or lockbox protocol evidence is incomplete.")
    if SELECTION_HARD_GATE_IDS[4] in failing_gate_ids:
        segments.append("Portability, tradability, or native validation still blocks advancement.")
    if SELECTION_HARD_GATE_IDS[5] in failing_gate_ids:
        segments.append("Account-fit rejects the current execution path.")
    if SELECTION_HARD_GATE_IDS[6] in failing_gate_ids:
        segments.append("Absolute-dollar viability or benchmark comparisons reject the candidate.")
    if SELECTION_HARD_GATE_IDS[7] in failing_gate_ids:
        segments.append("A single actual execution symbol is not pinned across the gate outputs.")
    if SELECTION_HARD_GATE_IDS[8] in failing_gate_ids:
        segments.append("Selection artifacts are incomplete.")
    if SELECTION_HARD_GATE_IDS[9] in failing_gate_ids:
        segments.append("Ranking attempted to override a failed hard gate.")
    if SELECTION_HARD_GATE_IDS[0] in failing_gate_ids:
        segments.append("Upstream reports are not aligned to one candidate and family.")
    return " ".join(segments)


def _build_remediation(
    decision: SelectionHardGatesDecision,
    checks: tuple[SelectionHardGateCheckResult, ...],
) -> str:
    failures = {check.gate_id: check for check in checks if not check.passed}
    if not failures:
        return "No remediation required."
    if decision == SelectionHardGatesDecision.PIVOT:
        return (
            "Pivot to a narrower or lower-touch promotion path before reconsidering this candidate."
        )
    if decision == SelectionHardGatesDecision.REJECT:
        return "Reject the current candidate from advancement until a materially different candidate exists."
    if SELECTION_HARD_GATE_IDS[7] in failures:
        return "Choose one actual execution symbol and keep every downstream gate aligned to it."
    if SELECTION_HARD_GATE_IDS[8] in failures:
        return (
            "Retain the selection manifest, logs, correlation IDs, expected-versus-actual diffs, and operator reasons."
        )
    return "Repair the failed prerequisite gates and rerun selection once the missing evidence is retained."


def evaluate_selection_hard_gates(
    request: SelectionHardGatesRequest,
) -> SelectionHardGatesReport:
    if request.schema_version != SUPPORTED_SELECTION_HARD_GATES_SCHEMA_VERSION:
        return _invalid_report(
            request,
            reason_code="SELECTION_HARD_GATES_UNSUPPORTED_SCHEMA_VERSION",
            explanation="Selection hard-gates request used an unsupported schema version.",
        )

    identity_check = _identity_check(request)
    if not identity_check.passed:
        return _invalid_report(
            request,
            reason_code=identity_check.reason_code,
            explanation=identity_check.explanation,
        )

    checks_without_ranking = (
        identity_check,
        _after_cost_profitability_check(request),
        _null_separation_check(request),
        _evaluation_protocol_check(request),
        _portability_tradability_check(request),
        _account_fit_check(request),
        _absolute_dollar_viability_check(request),
        _execution_symbol_pin_check(request),
        _selection_artifact_bundle_check(request),
    )

    provisional_decision, provisional_reason_code = _build_failure_decision(
        checks_without_ranking
    )
    ranking_check = _ranking_secondary_check(
        request=request,
        provisional_decision=provisional_decision,
        hard_gate_failures_present=any(
            not check.passed for check in checks_without_ranking[1:]
        ),
    )
    checks = checks_without_ranking + (ranking_check,)

    failing_checks = tuple(check for check in checks if not check.passed)
    if any(
        check.gate_id in {SELECTION_HARD_GATE_IDS[0], SELECTION_HARD_GATE_IDS[8]}
        for check in failing_checks
    ):
        status = SelectionHardGatesStatus.INVALID
        decision = SelectionHardGatesDecision.HOLD
        reason_code = next(
            check.reason_code
            for check in checks
            if check.gate_id in {SELECTION_HARD_GATE_IDS[0], SELECTION_HARD_GATE_IDS[8]}
            and not check.passed
        )
    elif failing_checks:
        status = SelectionHardGatesStatus.VIOLATION
        decision = provisional_decision
        reason_code = provisional_reason_code
    else:
        status = SelectionHardGatesStatus.PASS
        decision = SelectionHardGatesDecision.ADVANCE
        reason_code = "SELECTION_HARD_GATES_PASSED"

    selected_symbol = _selected_execution_symbol(request)
    retained_artifact_ids = _sorted_unique(
        [
            request.selection_artifact_bundle.artifact_manifest_id,
            *request.selection_artifact_bundle.expected_actual_diff_ids,
            *request.after_cost_profitability.retained_artifact_ids,
            *request.evaluation_protocol_report.retained_artifact_ids,
        ]
    )
    retained_log_ids = _sorted_unique(
        [
            *request.selection_artifact_bundle.retained_log_ids,
            *request.after_cost_profitability.retained_log_ids,
        ]
    )
    operator_reason_bundle = _sorted_unique(
        [
            *request.selection_artifact_bundle.operator_reason_bundle,
            *request.after_cost_profitability.operator_reason_bundle,
            *request.evaluation_protocol_report.operator_reason_bundle,
        ]
    )

    report = SelectionHardGatesReport(
        evaluation_id=request.evaluation_id,
        candidate_id=request.candidate_id,
        family_id=request.family_id,
        status=status,
        decision=decision,
        reason_code=reason_code,
        selected_execution_symbol=selected_symbol,
        hard_gates_passed=not failing_checks,
        secondary_ranking_considered=request.pareto_ranking is not None,
        triggered_gate_ids=tuple(check.gate_id for check in failing_checks),
        retained_artifact_ids=retained_artifact_ids,
        retained_log_ids=retained_log_ids,
        correlation_ids=request.selection_artifact_bundle.correlation_ids,
        expected_actual_diff_ids=request.selection_artifact_bundle.expected_actual_diff_ids,
        operator_reason_bundle=operator_reason_bundle,
        pareto_frontier_rank=(
            None if request.pareto_ranking is None else request.pareto_ranking.frontier_rank
        ),
        pareto_dominance_score=(
            None
            if request.pareto_ranking is None
            else request.pareto_ranking.dominance_score
        ),
        check_results=checks,
        explanation="",
        remediation="",
    )
    object.__setattr__(report, "explanation", _build_explanation(report))
    object.__setattr__(report, "remediation", _build_remediation(decision, checks))
    return report
