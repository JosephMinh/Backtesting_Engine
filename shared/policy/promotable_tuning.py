"""Promotable tuning protocol and mandatory research_run logging contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.guardrails import check_shared_kernel
from shared.policy.research_state import (
    FamilyDecisionLifecycle,
    FamilyDecisionRecord,
    FamilyDecisionType,
    ResearchRunRecord,
    ResearchStateMutationReport,
    ResearchStateStore,
    record_research_run,
)

SUPPORTED_PROMOTABLE_TUNING_SCHEMA_VERSION = 1


@unique
class TuningStage(str, Enum):
    LOCAL_SEARCH = "local_search"
    ROBUSTNESS_PERTURBATION = "robustness_perturbation"
    CANDIDATE_FREEZE = "candidate_freeze"


@unique
class TuningBatchOutcome(str, Enum):
    ADVANCE = "advance"
    REJECT = "reject"
    FREEZE = "freeze"


@unique
class TrialDisposition(str, Enum):
    RETAIN = "retain"
    PRUNE = "prune"
    FINALIST = "finalist"


@unique
class PromotableTuningStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    INVALID = "invalid"
    VIOLATION = "violation"


PROMOTABLE_TUNING_STAGE_ORDER = (
    TuningStage.LOCAL_SEARCH,
    TuningStage.ROBUSTNESS_PERTURBATION,
    TuningStage.CANDIDATE_FREEZE,
)

PROMOTABLE_TUNING_CHECK_IDS = (
    "continuation_decision_is_active_continue",
    "stage_progression_matches_protocol",
    "local_search_is_real_region_anchored",
    "deep_promotable_live_lane_requires_shared_kernel",
    "research_run_matches_batch_and_is_recorded",
    "rerunnable_inputs_are_recorded",
    "batch_logs_and_trial_artifacts_are_retained",
    "candidate_freeze_selects_single_finalist",
    "rejection_batches_preserve_reason_bundle",
)


def validate_promotable_tuning_contract() -> list[str]:
    errors: list[str] = []
    if SUPPORTED_PROMOTABLE_TUNING_SCHEMA_VERSION < 1:
        errors.append("supported schema version must be positive")
    if len(PROMOTABLE_TUNING_CHECK_IDS) != len(set(PROMOTABLE_TUNING_CHECK_IDS)):
        errors.append("promotable-tuning check identifiers must be unique")
    if len(PROMOTABLE_TUNING_STAGE_ORDER) != len(set(PROMOTABLE_TUNING_STAGE_ORDER)):
        errors.append("promotable-tuning stage order must be unique")
    if PROMOTABLE_TUNING_STAGE_ORDER != (
        TuningStage.LOCAL_SEARCH,
        TuningStage.ROBUSTNESS_PERTURBATION,
        TuningStage.CANDIDATE_FREEZE,
    ):
        errors.append("promotable-tuning stage order must match local-search, perturbation, freeze")
    return errors


VALIDATION_ERRORS = validate_promotable_tuning_contract()


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _require_mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}: must be an object")
    return value


def _require_present(payload: dict[str, object], *, field_name: str) -> object:
    if field_name not in payload:
        raise ValueError(f"{field_name} field is required")
    return payload[field_name]


def _require_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name}: must be a non-empty string")
    return value


def _require_optional_non_empty_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _require_string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list or tuple of strings")
    return tuple(
        _require_non_empty_string(item, field_name=f"{field_name}[]") for item in value
    )


def _require_object_sequence(
    value: object,
    *,
    field_name: str,
) -> tuple[dict[str, object], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name}: must be a list or tuple of objects")
    return tuple(
        _require_mapping(item, field_name=f"{field_name}[]")
        for item in value
    )


def _require_boolean(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name}: must be a boolean")
    return value


def _require_integer(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name}: must be an integer")
    return value


def _require_supported_schema_version(value: object, *, field_name: str) -> int:
    version = _require_integer(value, field_name=field_name)
    if version != SUPPORTED_PROMOTABLE_TUNING_SCHEMA_VERSION:
        raise ValueError(f"{field_name}: unsupported schema_version")
    return version


def _require_number_or_none(value: object, *, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name}: must be numeric or null")
    return float(value)


def _require_timestamp(value: object, *, field_name: str) -> str:
    try:
        normalized = datetime.datetime.fromisoformat(
            _require_non_empty_string(value, field_name=field_name).replace("Z", "+00:00")
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}: must be timezone-aware and ISO-8601 compatible") from exc
    if normalized.tzinfo is None:
        raise ValueError(f"{field_name}: must be timezone-aware and ISO-8601 compatible")
    return normalized.astimezone(datetime.timezone.utc).isoformat()


def _require_tuning_stage(value: object, *, field_name: str) -> TuningStage:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid tuning stage")
    try:
        return TuningStage(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid tuning stage") from exc


def _require_batch_outcome(value: object, *, field_name: str) -> TuningBatchOutcome:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid tuning batch outcome")
    try:
        return TuningBatchOutcome(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid tuning batch outcome") from exc


def _require_trial_disposition(value: object, *, field_name: str) -> TrialDisposition:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid trial disposition")
    try:
        return TrialDisposition(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid trial disposition") from exc


def _require_promotable_status(value: object, *, field_name: str) -> PromotableTuningStatus:
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: must be a valid promotable tuning status")
    try:
        return PromotableTuningStatus(value)
    except ValueError as exc:
        raise ValueError(f"{field_name}: must be a valid promotable tuning status") from exc


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
        raise ValueError(f"{label}: payload must decode to an object")
    return decoded


def _expected_prior_stages(stage: TuningStage) -> tuple[TuningStage, ...]:
    index = PROMOTABLE_TUNING_STAGE_ORDER.index(stage)
    return PROMOTABLE_TUNING_STAGE_ORDER[:index]


@dataclass(frozen=True)
class PromotableTrialRecord:
    trial_id: str
    parameter_reference_id: str
    seed: int
    objective_definition: str
    objective_value: float | None
    disposition: TrialDisposition
    pruning_reason: str | None = None
    retained_artifact_digests: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "trial_id": self.trial_id,
            "parameter_reference_id": self.parameter_reference_id,
            "seed": self.seed,
            "objective_definition": self.objective_definition,
            "objective_value": self.objective_value,
            "disposition": self.disposition.value,
            "pruning_reason": self.pruning_reason,
            "retained_artifact_digests": list(self.retained_artifact_digests),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PromotableTrialRecord:
        payload = _require_mapping(payload, field_name="promotable_trial_record")
        return cls(
            trial_id=_require_non_empty_string(
                _require_present(payload, field_name="trial_id"),
                field_name="trial_id",
            ),
            parameter_reference_id=_require_non_empty_string(
                _require_present(payload, field_name="parameter_reference_id"),
                field_name="parameter_reference_id",
            ),
            seed=_require_integer(
                _require_present(payload, field_name="seed"),
                field_name="seed",
            ),
            objective_definition=_require_non_empty_string(
                _require_present(payload, field_name="objective_definition"),
                field_name="objective_definition",
            ),
            objective_value=_require_number_or_none(
                _require_present(payload, field_name="objective_value"),
                field_name="objective_value",
            ),
            disposition=_require_trial_disposition(
                _require_present(payload, field_name="disposition"),
                field_name="disposition",
            ),
            pruning_reason=(
                None
                if payload.get("pruning_reason") is None
                else _require_non_empty_string(
                    payload["pruning_reason"],
                    field_name="pruning_reason",
                )
            ),
            retained_artifact_digests=_require_string_sequence(
                payload.get("retained_artifact_digests", []),
                field_name="retained_artifact_digests",
            ),
        )


@dataclass(frozen=True)
class PromotableTuningRequest:
    evaluation_id: str
    family_id: str
    subfamily_id: str
    stage: TuningStage
    continuation_decision: FamilyDecisionRecord
    research_run: ResearchRunRecord
    trials: tuple[PromotableTrialRecord, ...]
    batch_outcome: TuningBatchOutcome
    structured_log_artifact_digests: tuple[str, ...]
    prior_completed_stages: tuple[TuningStage, ...] = ()
    live_eligible: bool = True
    deep_promotable_tuning: bool = False
    real_region_reference: str | None = None
    research_kernel_hash: str = ""
    live_kernel_hash: str = ""
    replay_manifest_id: str | None = None
    replay_command: str | None = None
    batch_reason_bundle: tuple[str, ...] = ()
    schema_version: int = SUPPORTED_PROMOTABLE_TUNING_SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "family_id": self.family_id,
            "subfamily_id": self.subfamily_id,
            "stage": self.stage.value,
            "continuation_decision": self.continuation_decision.to_dict(),
            "research_run": self.research_run.to_dict(),
            "trials": [trial.to_dict() for trial in self.trials],
            "batch_outcome": self.batch_outcome.value,
            "structured_log_artifact_digests": list(self.structured_log_artifact_digests),
            "prior_completed_stages": [
                stage.value for stage in self.prior_completed_stages
            ],
            "live_eligible": self.live_eligible,
            "deep_promotable_tuning": self.deep_promotable_tuning,
            "real_region_reference": self.real_region_reference,
            "research_kernel_hash": self.research_kernel_hash,
            "live_kernel_hash": self.live_kernel_hash,
            "replay_manifest_id": self.replay_manifest_id,
            "replay_command": self.replay_command,
            "batch_reason_bundle": list(self.batch_reason_bundle),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PromotableTuningRequest:
        payload = _require_mapping(payload, field_name="promotable_tuning_request")
        return cls(
            evaluation_id=_require_non_empty_string(
                _require_present(payload, field_name="evaluation_id"),
                field_name="evaluation_id",
            ),
            family_id=_require_non_empty_string(
                _require_present(payload, field_name="family_id"),
                field_name="family_id",
            ),
            subfamily_id=_require_non_empty_string(
                _require_present(payload, field_name="subfamily_id"),
                field_name="subfamily_id",
            ),
            stage=_require_tuning_stage(
                _require_present(payload, field_name="stage"),
                field_name="stage",
            ),
            continuation_decision=FamilyDecisionRecord.from_dict(
                _require_mapping(
                    _require_present(payload, field_name="continuation_decision"),
                    field_name="continuation_decision",
                )
            ),
            research_run=ResearchRunRecord.from_dict(
                _require_mapping(
                    _require_present(payload, field_name="research_run"),
                    field_name="research_run",
                )
            ),
            trials=tuple(
                PromotableTrialRecord.from_dict(item)
                for item in _require_object_sequence(
                    _require_present(payload, field_name="trials"),
                    field_name="trials",
                )
            ),
            batch_outcome=_require_batch_outcome(
                _require_present(payload, field_name="batch_outcome"),
                field_name="batch_outcome",
            ),
            structured_log_artifact_digests=_require_string_sequence(
                payload.get("structured_log_artifact_digests", []),
                field_name="structured_log_artifact_digests",
            ),
            prior_completed_stages=tuple(
                _require_tuning_stage(item, field_name="prior_completed_stages[]")
                for item in payload.get("prior_completed_stages", [])
            ),
            live_eligible=(
                True
                if payload.get("live_eligible") is None
                else _require_boolean(payload["live_eligible"], field_name="live_eligible")
            ),
            deep_promotable_tuning=(
                False
                if payload.get("deep_promotable_tuning") is None
                else _require_boolean(
                    payload["deep_promotable_tuning"],
                    field_name="deep_promotable_tuning",
                )
            ),
            real_region_reference=(
                None
                if payload.get("real_region_reference") is None
                else _require_non_empty_string(
                    payload["real_region_reference"],
                    field_name="real_region_reference",
                )
            ),
            research_kernel_hash=(
                ""
                if payload.get("research_kernel_hash") is None
                else _require_non_empty_string(
                    payload["research_kernel_hash"],
                    field_name="research_kernel_hash",
                )
            ),
            live_kernel_hash=(
                ""
                if payload.get("live_kernel_hash") is None
                else _require_non_empty_string(
                    payload["live_kernel_hash"],
                    field_name="live_kernel_hash",
                )
            ),
            replay_manifest_id=(
                None
                if payload.get("replay_manifest_id") is None
                else _require_non_empty_string(
                    payload["replay_manifest_id"],
                    field_name="replay_manifest_id",
                )
            ),
            replay_command=(
                None
                if payload.get("replay_command") is None
                else _require_non_empty_string(
                    payload["replay_command"],
                    field_name="replay_command",
                )
            ),
            batch_reason_bundle=_require_string_sequence(
                payload.get("batch_reason_bundle", []),
                field_name="batch_reason_bundle",
            ),
            schema_version=_require_supported_schema_version(
                _require_present(payload, field_name="schema_version"),
                field_name="schema_version",
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> PromotableTuningRequest:
        return cls.from_dict(
            _decode_json_object(payload, label="promotable_tuning_request")
        )


@dataclass(frozen=True)
class PromotableTuningCheckResult:
    check_id: str
    passed: bool
    reason_code: str
    explanation: str
    context: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "context": _jsonable(self.context),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PromotableTuningCheckResult:
        payload = _require_mapping(payload, field_name="promotable_tuning_check_result")
        return cls(
            check_id=_require_non_empty_string(
                _require_present(payload, field_name="check_id"),
                field_name="check_id",
            ),
            passed=_require_boolean(
                _require_present(payload, field_name="passed"),
                field_name="passed",
            ),
            reason_code=_require_non_empty_string(
                _require_present(payload, field_name="reason_code"),
                field_name="reason_code",
            ),
            explanation=_require_non_empty_string(
                _require_present(payload, field_name="explanation"),
                field_name="explanation",
            ),
            context=_require_mapping(
                _require_present(payload, field_name="context"),
                field_name="context",
            ),
        )


@dataclass(frozen=True)
class PromotableTuningReport:
    evaluation_id: str
    family_id: str
    subfamily_id: str
    stage: TuningStage
    status: PromotableTuningStatus
    batch_outcome: TuningBatchOutcome
    continuation_approved: bool
    shared_kernel_gate_required: bool
    shared_kernel_gate_passed: bool
    research_run_recorded: bool
    replayable: bool
    promotable_trial_ids: tuple[str, ...]
    pruned_trial_ids: tuple[str, ...]
    finalist_trial_id: str | None
    structured_log_artifact_digests: tuple[str, ...]
    batch_reason_bundle: tuple[str, ...]
    check_results: tuple[PromotableTuningCheckResult, ...]
    research_run_report: ResearchStateMutationReport
    generated_at_utc: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "family_id": self.family_id,
            "subfamily_id": self.subfamily_id,
            "stage": self.stage.value,
            "status": self.status.value,
            "batch_outcome": self.batch_outcome.value,
            "continuation_approved": self.continuation_approved,
            "shared_kernel_gate_required": self.shared_kernel_gate_required,
            "shared_kernel_gate_passed": self.shared_kernel_gate_passed,
            "research_run_recorded": self.research_run_recorded,
            "replayable": self.replayable,
            "promotable_trial_ids": list(self.promotable_trial_ids),
            "pruned_trial_ids": list(self.pruned_trial_ids),
            "finalist_trial_id": self.finalist_trial_id,
            "structured_log_artifact_digests": list(
                self.structured_log_artifact_digests
            ),
            "batch_reason_bundle": list(self.batch_reason_bundle),
            "check_results": [result.to_dict() for result in self.check_results],
            "research_run_report": self.research_run_report.to_dict(),
            "generated_at_utc": self.generated_at_utc,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> PromotableTuningReport:
        payload = _require_mapping(payload, field_name="promotable_tuning_report")
        return cls(
            evaluation_id=_require_non_empty_string(
                _require_present(payload, field_name="evaluation_id"),
                field_name="evaluation_id",
            ),
            family_id=_require_non_empty_string(
                _require_present(payload, field_name="family_id"),
                field_name="family_id",
            ),
            subfamily_id=_require_non_empty_string(
                _require_present(payload, field_name="subfamily_id"),
                field_name="subfamily_id",
            ),
            stage=_require_tuning_stage(
                _require_present(payload, field_name="stage"),
                field_name="stage",
            ),
            status=_require_promotable_status(
                _require_present(payload, field_name="status"),
                field_name="status",
            ),
            batch_outcome=_require_batch_outcome(
                _require_present(payload, field_name="batch_outcome"),
                field_name="batch_outcome",
            ),
            continuation_approved=_require_boolean(
                _require_present(payload, field_name="continuation_approved"),
                field_name="continuation_approved",
            ),
            shared_kernel_gate_required=_require_boolean(
                _require_present(payload, field_name="shared_kernel_gate_required"),
                field_name="shared_kernel_gate_required",
            ),
            shared_kernel_gate_passed=_require_boolean(
                _require_present(payload, field_name="shared_kernel_gate_passed"),
                field_name="shared_kernel_gate_passed",
            ),
            research_run_recorded=_require_boolean(
                _require_present(payload, field_name="research_run_recorded"),
                field_name="research_run_recorded",
            ),
            replayable=_require_boolean(
                _require_present(payload, field_name="replayable"),
                field_name="replayable",
            ),
            promotable_trial_ids=_require_string_sequence(
                _require_present(payload, field_name="promotable_trial_ids"),
                field_name="promotable_trial_ids",
            ),
            pruned_trial_ids=_require_string_sequence(
                _require_present(payload, field_name="pruned_trial_ids"),
                field_name="pruned_trial_ids",
            ),
            finalist_trial_id=(
                None
                if _require_present(payload, field_name="finalist_trial_id") is None
                else _require_non_empty_string(
                    payload["finalist_trial_id"],
                    field_name="finalist_trial_id",
                )
            ),
            structured_log_artifact_digests=_require_string_sequence(
                _require_present(payload, field_name="structured_log_artifact_digests"),
                field_name="structured_log_artifact_digests",
            ),
            batch_reason_bundle=_require_string_sequence(
                _require_present(payload, field_name="batch_reason_bundle"),
                field_name="batch_reason_bundle",
            ),
            check_results=tuple(
                PromotableTuningCheckResult.from_dict(item)
                for item in _require_object_sequence(
                    _require_present(payload, field_name="check_results"),
                    field_name="check_results",
                )
            ),
            research_run_report=ResearchStateMutationReport.from_dict(
                _require_mapping(
                    _require_present(payload, field_name="research_run_report"),
                    field_name="research_run_report",
                )
            ),
            generated_at_utc=_require_timestamp(
                _require_present(payload, field_name="generated_at_utc"),
                field_name="generated_at_utc",
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> PromotableTuningReport:
        return cls.from_dict(
            _decode_json_object(payload, label="promotable_tuning_report")
        )


def _check(
    check_id: str,
    *,
    passed: bool,
    reason_code: str,
    explanation: str,
    context: dict[str, object] | None = None,
) -> PromotableTuningCheckResult:
    return PromotableTuningCheckResult(
        check_id=check_id,
        passed=passed,
        reason_code=reason_code,
        explanation=explanation,
        context={} if context is None else context,
    )


def _evaluate_continuation_check(
    request: PromotableTuningRequest,
) -> tuple[bool, PromotableTuningCheckResult]:
    decision = request.continuation_decision
    continuation_approved = (
        decision.family_id == request.family_id
        and decision.decision_type == FamilyDecisionType.CONTINUE
        and decision.lifecycle_state == FamilyDecisionLifecycle.ACTIVE
        and decision.next_budget_authorized_usd > 0
        and bool(decision.evidence_references)
        and bool(decision.reviewer_self_attestations)
    )
    return continuation_approved, _check(
        PROMOTABLE_TUNING_CHECK_IDS[0],
        passed=continuation_approved,
        reason_code=(
            "PROMOTABLE_TUNING_CONTINUATION_APPROVED"
            if continuation_approved
            else "PROMOTABLE_TUNING_CONTINUATION_REQUIRED"
        ),
        explanation=(
            "Promotable tuning is backed by an active continuation decision with evidence, budget, and reviewer attestations."
            if continuation_approved
            else "Promotable tuning requires an active continue decision for the same family with evidence, budget, and reviewer attestations."
        ),
        context={
            "decision_record_id": decision.decision_record_id,
            "decision_type": decision.decision_type.value,
            "decision_family_id": decision.family_id,
            "decision_lifecycle_state": decision.lifecycle_state.value,
            "next_budget_authorized_usd": decision.next_budget_authorized_usd,
        },
    )


def _evaluate_stage_progression(
    request: PromotableTuningRequest,
) -> PromotableTuningCheckResult:
    expected = _expected_prior_stages(request.stage)
    passed = request.prior_completed_stages == expected
    return _check(
        PROMOTABLE_TUNING_CHECK_IDS[1],
        passed=passed,
        reason_code=(
            "PROMOTABLE_TUNING_STAGE_SEQUENCE_VALID"
            if passed
            else "PROMOTABLE_TUNING_STAGE_SEQUENCE_INVALID"
        ),
        explanation=(
            "Promotable tuning stage matches the required local-search, perturbation, freeze progression."
            if passed
            else "Promotable tuning stages must advance strictly from local search to perturbation to candidate freeze."
        ),
        context={
            "stage": request.stage.value,
            "expected_prior_stages": [stage.value for stage in expected],
            "prior_completed_stages": [
                stage.value for stage in request.prior_completed_stages
            ],
        },
    )


def _evaluate_real_region_anchor(
    request: PromotableTuningRequest,
) -> PromotableTuningCheckResult:
    if request.stage != TuningStage.LOCAL_SEARCH:
        return _check(
            PROMOTABLE_TUNING_CHECK_IDS[2],
            passed=True,
            reason_code="PROMOTABLE_TUNING_REAL_REGION_ANCHOR_NOT_REQUIRED",
            explanation="Real-region anchoring is only evaluated for the local-search stage.",
            context={"stage": request.stage.value},
        )
    passed = bool(request.real_region_reference)
    return _check(
        PROMOTABLE_TUNING_CHECK_IDS[2],
        passed=passed,
        reason_code=(
            "PROMOTABLE_TUNING_REAL_REGION_ANCHOR_VALID"
            if passed
            else "PROMOTABLE_TUNING_REAL_REGION_ANCHOR_REQUIRED"
        ),
        explanation=(
            "Local search is anchored to a real parameter region rather than an implausible global sweep."
            if passed
            else "Local search must reference the real parameter region it is refining."
        ),
        context={
            "stage": request.stage.value,
            "real_region_reference": request.real_region_reference,
        },
    )


def _evaluate_shared_kernel_gate(
    request: PromotableTuningRequest,
) -> tuple[bool, PromotableTuningCheckResult]:
    required = request.live_eligible and request.deep_promotable_tuning
    if not required:
        return required, _check(
            PROMOTABLE_TUNING_CHECK_IDS[3],
            passed=True,
            reason_code="PROMOTABLE_TUNING_SHARED_KERNEL_NOT_REQUIRED",
            explanation="Shared-kernel parity is only required for live-eligible deep promotable tuning.",
            context={
                "live_eligible": request.live_eligible,
                "deep_promotable_tuning": request.deep_promotable_tuning,
            },
        )

    guardrail = check_shared_kernel(
        research_kernel_hash=request.research_kernel_hash,
        live_kernel_hash=request.live_kernel_hash,
        diagnostic=(
            "Live-eligible deep promotable tuning must stay on the canonical shared kernel before lockbox entry."
        ),
    )
    return required, _check(
        PROMOTABLE_TUNING_CHECK_IDS[3],
        passed=guardrail.passed,
        reason_code=(
            "PROMOTABLE_TUNING_SHARED_KERNEL_ALIGNED"
            if guardrail.passed
            else guardrail.reason_code
        ),
        explanation=(
            "Deep promotable tuning remains on the canonical shared kernel."
            if guardrail.passed
            else "Live-eligible deep promotable tuning is blocked until research and live kernel hashes match."
        ),
        context={"guardrail_trace": guardrail.to_dict()},
    )


def _record_batch_research_run(
    store: ResearchStateStore,
    request: PromotableTuningRequest,
) -> tuple[ResearchStateMutationReport, PromotableTuningCheckResult]:
    run = request.research_run
    if run.family_id != request.family_id or run.subfamily_id != request.subfamily_id:
        report = ResearchStateMutationReport(
            record_type="research_run",
            record_id=run.research_run_id,
            operation="create",
            status="invalid",
            reason_code="PROMOTABLE_TUNING_RESEARCH_RUN_SCOPE_MISMATCH",
            previous_state=None,
            next_state=run.lifecycle_state.value,
            explanation=(
                "Promotable tuning batch must record a research_run for the same family and subfamily."
            ),
        )
    else:
        report = record_research_run(store, run)

    return report, _check(
        PROMOTABLE_TUNING_CHECK_IDS[4],
        passed=report.status == "pass",
        reason_code=(
            "PROMOTABLE_TUNING_RESEARCH_RUN_RECORDED"
            if report.status == "pass"
            else report.reason_code
        ),
        explanation=(
            "Promotable batch execution produced a canonical research_run record."
            if report.status == "pass"
            else "Promotable batch execution must produce a canonical research_run record, even when the batch rejects the candidate."
        ),
        context={"research_run_report": report.to_dict()},
    )


def _evaluate_replayability(
    request: PromotableTuningRequest,
) -> tuple[bool, PromotableTuningCheckResult]:
    required_fields = {
        "environment_lock_id": request.research_run.environment_lock_id,
        "dataset_release_id": request.research_run.dataset_release_id,
        "analytic_release_id": request.research_run.analytic_release_id,
        "data_profile_release_id": request.research_run.data_profile_release_id,
        "execution_profile_id": request.research_run.execution_profile_id,
        "parameter_reference_id": request.research_run.parameter_reference_id,
        "policy_bundle_hash": request.research_run.policy_bundle_hash,
        "compatibility_matrix_version": request.research_run.compatibility_matrix_version,
        "replay_manifest_id": request.replay_manifest_id,
        "replay_command": request.replay_command,
    }
    missing_fields = tuple(
        field_name
        for field_name, value in required_fields.items()
        if value is None or str(value) == ""
    )
    recorded_seed_set = set(request.research_run.seeds)
    trial_seed_set = {trial.seed for trial in request.trials}
    missing_trial_seeds = tuple(
        seed for seed in sorted(trial_seed_set) if seed not in recorded_seed_set
    )
    replayable = not missing_fields and not missing_trial_seeds
    return replayable, _check(
        PROMOTABLE_TUNING_CHECK_IDS[5],
        passed=replayable,
        reason_code=(
            "PROMOTABLE_TUNING_REPLAY_MATERIAL_COMPLETE"
            if replayable
            else "PROMOTABLE_TUNING_REPLAY_MATERIAL_MISSING"
        ),
        explanation=(
            "Promotable tuning can be rerun from recorded releases, locks, seeds, and replay metadata."
            if replayable
            else "Promotable tuning must retain the full replay bundle, including recorded seeds and replay metadata."
        ),
        context={
            "missing_fields": list(missing_fields),
            "missing_trial_seeds": list(missing_trial_seeds),
            "research_run_id": request.research_run.research_run_id,
        },
    )


def _evaluate_logging_and_artifacts(
    request: PromotableTuningRequest,
) -> PromotableTuningCheckResult:
    duplicate_trial_ids = tuple(
        sorted(
            {
                trial.trial_id
                for trial in request.trials
                if sum(
                    1 for candidate in request.trials if candidate.trial_id == trial.trial_id
                )
                > 1
            }
        )
    )
    missing_parameter_references = tuple(
        trial.trial_id for trial in request.trials if not trial.parameter_reference_id
    )
    missing_objective_definitions = tuple(
        trial.trial_id for trial in request.trials if not trial.objective_definition
    )
    missing_trial_artifacts = tuple(
        trial.trial_id for trial in request.trials if not trial.retained_artifact_digests
    )
    missing_pruning_reasons = tuple(
        trial.trial_id
        for trial in request.trials
        if trial.disposition == TrialDisposition.PRUNE and not trial.pruning_reason
    )
    passed = (
        bool(request.trials)
        and bool(request.structured_log_artifact_digests)
        and not duplicate_trial_ids
        and not missing_parameter_references
        and not missing_objective_definitions
        and not missing_trial_artifacts
        and not missing_pruning_reasons
    )
    return _check(
        PROMOTABLE_TUNING_CHECK_IDS[6],
        passed=passed,
        reason_code=(
            "PROMOTABLE_TUNING_LOGGING_AND_ARTIFACTS_COMPLETE"
            if passed
            else "PROMOTABLE_TUNING_LOGGING_AND_ARTIFACTS_INCOMPLETE"
        ),
        explanation=(
            "Promotable tuning retained detailed batch logs, trial objectives, pruning reasons, and artifacts."
            if passed
            else "Promotable tuning must retain batch logs plus objective definitions, pruning reasons, and artifacts for every trial."
        ),
        context={
            "structured_log_artifact_digests": list(
                request.structured_log_artifact_digests
            ),
            "duplicate_trial_ids": list(duplicate_trial_ids),
            "missing_parameter_references": list(missing_parameter_references),
            "missing_objective_definitions": list(missing_objective_definitions),
            "missing_trial_artifacts": list(missing_trial_artifacts),
            "missing_pruning_reasons": list(missing_pruning_reasons),
        },
    )


def _evaluate_candidate_freeze(
    request: PromotableTuningRequest,
    finalists: tuple[str, ...],
) -> PromotableTuningCheckResult:
    if request.stage != TuningStage.CANDIDATE_FREEZE:
        return _check(
            PROMOTABLE_TUNING_CHECK_IDS[7],
            passed=True,
            reason_code="PROMOTABLE_TUNING_CANDIDATE_FREEZE_NOT_REQUIRED",
            explanation="Candidate-freeze finalist selection is only evaluated during the freeze stage.",
            context={"stage": request.stage.value},
        )
    passed = len(finalists) == 1 and request.batch_outcome == TuningBatchOutcome.FREEZE
    return _check(
        PROMOTABLE_TUNING_CHECK_IDS[7],
        passed=passed,
        reason_code=(
            "PROMOTABLE_TUNING_FINALIST_SELECTED"
            if passed
            else "PROMOTABLE_TUNING_FINALIST_SELECTION_INVALID"
        ),
        explanation=(
            "Candidate freeze selected exactly one finalist and sealed the batch outcome."
            if passed
            else "Candidate freeze must select exactly one finalist and emit a freeze outcome."
        ),
        context={
            "stage": request.stage.value,
            "batch_outcome": request.batch_outcome.value,
            "finalist_trial_ids": list(finalists),
        },
    )


def _evaluate_rejection_reason_bundle(
    request: PromotableTuningRequest,
) -> PromotableTuningCheckResult:
    if request.batch_outcome != TuningBatchOutcome.REJECT:
        return _check(
            PROMOTABLE_TUNING_CHECK_IDS[8],
            passed=True,
            reason_code="PROMOTABLE_TUNING_REJECTION_REASON_BUNDLE_NOT_REQUIRED",
            explanation="Rejection reason bundles are only required for rejected batches.",
            context={"batch_outcome": request.batch_outcome.value},
        )
    passed = bool(request.batch_reason_bundle)
    return _check(
        PROMOTABLE_TUNING_CHECK_IDS[8],
        passed=passed,
        reason_code=(
            "PROMOTABLE_TUNING_REJECTION_REASON_BUNDLE_RECORDED"
            if passed
            else "PROMOTABLE_TUNING_REJECTION_REASON_BUNDLE_REQUIRED"
        ),
        explanation=(
            "Rejected promotable batches retain a reason bundle for later audit."
            if passed
            else "Rejected promotable batches must retain a reason bundle, not just a missing finalist."
        ),
        context={"batch_reason_bundle": list(request.batch_reason_bundle)},
    )


def evaluate_promotable_tuning(
    store: ResearchStateStore,
    request: PromotableTuningRequest,
) -> PromotableTuningReport:
    if request.schema_version != SUPPORTED_PROMOTABLE_TUNING_SCHEMA_VERSION:
        invalid_report = ResearchStateMutationReport(
            record_type="research_run",
            record_id=request.research_run.research_run_id,
            operation="create",
            status="invalid",
            reason_code="PROMOTABLE_TUNING_UNSUPPORTED_SCHEMA_VERSION",
            previous_state=None,
            next_state=request.research_run.lifecycle_state.value,
            explanation="Promotable tuning request used an unsupported schema version.",
        )
        check_results = (
            _check(
                PROMOTABLE_TUNING_CHECK_IDS[0],
                passed=False,
                reason_code="PROMOTABLE_TUNING_UNSUPPORTED_SCHEMA_VERSION",
                explanation="Promotable tuning request used an unsupported schema version.",
                context={"schema_version": request.schema_version},
            ),
        )
        return PromotableTuningReport(
            evaluation_id=request.evaluation_id,
            family_id=request.family_id,
            subfamily_id=request.subfamily_id,
            stage=request.stage,
            status=PromotableTuningStatus.INVALID,
            batch_outcome=request.batch_outcome,
            continuation_approved=False,
            shared_kernel_gate_required=False,
            shared_kernel_gate_passed=False,
            research_run_recorded=False,
            replayable=False,
            promotable_trial_ids=tuple(trial.trial_id for trial in request.trials),
            pruned_trial_ids=(),
            finalist_trial_id=None,
            structured_log_artifact_digests=request.structured_log_artifact_digests,
            batch_reason_bundle=request.batch_reason_bundle,
            check_results=check_results,
            research_run_report=invalid_report,
        )

    continuation_approved, continuation_check = _evaluate_continuation_check(request)
    stage_check = _evaluate_stage_progression(request)
    real_region_check = _evaluate_real_region_anchor(request)
    shared_kernel_gate_required, shared_kernel_check = _evaluate_shared_kernel_gate(
        request
    )
    research_run_report, research_run_check = _record_batch_research_run(store, request)
    replayable, replay_check = _evaluate_replayability(request)
    logging_check = _evaluate_logging_and_artifacts(request)
    finalists = tuple(
        trial.trial_id
        for trial in request.trials
        if trial.disposition == TrialDisposition.FINALIST
    )
    candidate_freeze_check = _evaluate_candidate_freeze(request, finalists)
    rejection_reason_check = _evaluate_rejection_reason_bundle(request)

    check_results = (
        continuation_check,
        stage_check,
        real_region_check,
        shared_kernel_check,
        research_run_check,
        replay_check,
        logging_check,
        candidate_freeze_check,
        rejection_reason_check,
    )

    invalid_failures = {
        PROMOTABLE_TUNING_CHECK_IDS[1],
        PROMOTABLE_TUNING_CHECK_IDS[4],
        PROMOTABLE_TUNING_CHECK_IDS[5],
        PROMOTABLE_TUNING_CHECK_IDS[6],
    }
    failed_ids = {result.check_id for result in check_results if not result.passed}
    if failed_ids & invalid_failures:
        status = PromotableTuningStatus.INVALID
    elif failed_ids:
        status = PromotableTuningStatus.VIOLATION
    else:
        status = PromotableTuningStatus.PASS

    return PromotableTuningReport(
        evaluation_id=request.evaluation_id,
        family_id=request.family_id,
        subfamily_id=request.subfamily_id,
        stage=request.stage,
        status=status,
        batch_outcome=request.batch_outcome,
        continuation_approved=continuation_approved,
        shared_kernel_gate_required=shared_kernel_gate_required,
        shared_kernel_gate_passed=shared_kernel_check.passed,
        research_run_recorded=research_run_check.passed,
        replayable=replayable,
        promotable_trial_ids=tuple(trial.trial_id for trial in request.trials),
        pruned_trial_ids=tuple(
            trial.trial_id
            for trial in request.trials
            if trial.disposition == TrialDisposition.PRUNE
        ),
        finalist_trial_id=finalists[0] if len(finalists) == 1 else None,
        structured_log_artifact_digests=request.structured_log_artifact_digests,
        batch_reason_bundle=request.batch_reason_bundle,
        check_results=check_results,
        research_run_report=research_run_report,
    )
