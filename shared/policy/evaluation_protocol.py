"""Walk-forward, robustness, omission, and candidate-freeze protocol contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any


SUPPORTED_EVALUATION_PROTOCOL_SCHEMA_VERSION = 1
REQUIRED_EVALUATION_STAGE_ORDER = (
    "screening",
    "validation",
    "stress",
    "omission",
    "lockbox",
    "candidate_freeze",
)
REQUIRED_OMISSION_DIMENSIONS = (
    "regime",
    "segment",
    "anchor",
    "event_cluster",
)
EVALUATION_PROTOCOL_CHECK_IDS = (
    "EP01",
    "EP02",
    "EP03",
    "EP04",
    "EP05",
    "EP06",
    "EP07",
    "EP08",
    "EP09",
)


def _utcnow() -> str:
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


def _sorted_unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


@unique
class EvaluationStage(str, Enum):
    SCREENING = "screening"
    VALIDATION = "validation"
    STRESS = "stress"
    OMISSION = "omission"
    LOCKBOX = "lockbox"
    CANDIDATE_FREEZE = "candidate_freeze"


@unique
class OmissionDimension(str, Enum):
    REGIME = "regime"
    SEGMENT = "segment"
    ANCHOR = "anchor"
    EVENT_CLUSTER = "event_cluster"


@unique
class EvaluationProtocolStatus(str, Enum):
    PASS = "pass"  # nosec B105 - policy status literal, not a credential
    VIOLATION = "violation"
    INVALID = "invalid"


@unique
class EvaluationProtocolDecision(str, Enum):
    FREEZE_CANDIDATE = "freeze_candidate"
    HOLD = "hold"
    REPAIR_PROTOCOL = "repair_protocol"


@dataclass(frozen=True)
class EvaluationArtifactBundle:
    artifact_manifest_id: str
    retained_log_ids: tuple[str, ...]
    correlation_ids: tuple[str, ...]
    expected_actual_diff_ids: tuple[str, ...]
    operator_reason_bundle: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_manifest_id": self.artifact_manifest_id,
            "retained_log_ids": list(self.retained_log_ids),
            "correlation_ids": list(self.correlation_ids),
            "expected_actual_diff_ids": list(self.expected_actual_diff_ids),
            "operator_reason_bundle": list(self.operator_reason_bundle),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationArtifactBundle":
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


@dataclass(frozen=True)
class EvaluationStageRecord:
    stage: EvaluationStage
    completed: bool
    research_run_id: str
    artifact_bundle: EvaluationArtifactBundle

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "completed": self.completed,
            "research_run_id": self.research_run_id,
            "artifact_bundle": self.artifact_bundle.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationStageRecord":
        return cls(
            stage=EvaluationStage(str(payload["stage"])),
            completed=bool(payload["completed"]),
            research_run_id=str(payload["research_run_id"]),
            artifact_bundle=EvaluationArtifactBundle.from_dict(
                dict(payload["artifact_bundle"])
            ),
        )


@dataclass(frozen=True)
class WalkForwardFoldEvidence:
    fold_id: str
    training_window_id: str
    validation_window_id: str
    parameter_set_id: str
    passed: bool
    artifact_bundle: EvaluationArtifactBundle

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold_id": self.fold_id,
            "training_window_id": self.training_window_id,
            "validation_window_id": self.validation_window_id,
            "parameter_set_id": self.parameter_set_id,
            "passed": self.passed,
            "artifact_bundle": self.artifact_bundle.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WalkForwardFoldEvidence":
        return cls(
            fold_id=str(payload["fold_id"]),
            training_window_id=str(payload["training_window_id"]),
            validation_window_id=str(payload["validation_window_id"]),
            parameter_set_id=str(payload["parameter_set_id"]),
            passed=bool(payload["passed"]),
            artifact_bundle=EvaluationArtifactBundle.from_dict(
                dict(payload["artifact_bundle"])
            ),
        )


@dataclass(frozen=True)
class ParameterStabilityEvidence:
    parameter_id: str
    stability_ratio: float
    allowed_stability_ratio: float
    passed: bool
    artifact_bundle: EvaluationArtifactBundle

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter_id": self.parameter_id,
            "stability_ratio": self.stability_ratio,
            "allowed_stability_ratio": self.allowed_stability_ratio,
            "passed": self.passed,
            "artifact_bundle": self.artifact_bundle.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ParameterStabilityEvidence":
        return cls(
            parameter_id=str(payload["parameter_id"]),
            stability_ratio=float(payload["stability_ratio"]),
            allowed_stability_ratio=float(payload["allowed_stability_ratio"]),
            passed=bool(payload["passed"]),
            artifact_bundle=EvaluationArtifactBundle.from_dict(
                dict(payload["artifact_bundle"])
            ),
        )


@dataclass(frozen=True)
class BootstrapIntervalEvidence:
    metric_id: str
    block_length_bars: int
    resample_count: int
    confidence_level: float
    lower_bound: float
    upper_bound: float
    minimum_acceptable_edge: float
    passed: bool
    artifact_bundle: EvaluationArtifactBundle

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "block_length_bars": self.block_length_bars,
            "resample_count": self.resample_count,
            "confidence_level": self.confidence_level,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "minimum_acceptable_edge": self.minimum_acceptable_edge,
            "passed": self.passed,
            "artifact_bundle": self.artifact_bundle.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BootstrapIntervalEvidence":
        return cls(
            metric_id=str(payload["metric_id"]),
            block_length_bars=int(payload["block_length_bars"]),
            resample_count=int(payload["resample_count"]),
            confidence_level=float(payload["confidence_level"]),
            lower_bound=float(payload["lower_bound"]),
            upper_bound=float(payload["upper_bound"]),
            minimum_acceptable_edge=float(payload["minimum_acceptable_edge"]),
            passed=bool(payload["passed"]),
            artifact_bundle=EvaluationArtifactBundle.from_dict(
                dict(payload["artifact_bundle"])
            ),
        )


@dataclass(frozen=True)
class OmissionCheckEvidence:
    omission_dimension: OmissionDimension
    omitted_slice_id: str
    passed: bool
    artifact_bundle: EvaluationArtifactBundle

    def to_dict(self) -> dict[str, Any]:
        return {
            "omission_dimension": self.omission_dimension.value,
            "omitted_slice_id": self.omitted_slice_id,
            "passed": self.passed,
            "artifact_bundle": self.artifact_bundle.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OmissionCheckEvidence":
        return cls(
            omission_dimension=OmissionDimension(str(payload["omission_dimension"])),
            omitted_slice_id=str(payload["omitted_slice_id"]),
            passed=bool(payload["passed"]),
            artifact_bundle=EvaluationArtifactBundle.from_dict(
                dict(payload["artifact_bundle"])
            ),
        )


@dataclass(frozen=True)
class PowerAnalysisEvidence:
    metric_id: str
    estimated_edge_bps: float
    minimum_detectable_edge_bps: float
    power: float
    minimum_required_power: float
    sample_count: int
    minimum_required_sample_count: int
    artifact_bundle: EvaluationArtifactBundle

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "estimated_edge_bps": self.estimated_edge_bps,
            "minimum_detectable_edge_bps": self.minimum_detectable_edge_bps,
            "power": self.power,
            "minimum_required_power": self.minimum_required_power,
            "sample_count": self.sample_count,
            "minimum_required_sample_count": self.minimum_required_sample_count,
            "artifact_bundle": self.artifact_bundle.to_dict(),
        }

    @property
    def approved_for_deep_tuning(self) -> bool:
        return (
            self.estimated_edge_bps >= self.minimum_detectable_edge_bps
            and self.power >= self.minimum_required_power
            and self.sample_count >= self.minimum_required_sample_count
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PowerAnalysisEvidence":
        return cls(
            metric_id=str(payload["metric_id"]),
            estimated_edge_bps=float(payload["estimated_edge_bps"]),
            minimum_detectable_edge_bps=float(payload["minimum_detectable_edge_bps"]),
            power=float(payload["power"]),
            minimum_required_power=float(payload["minimum_required_power"]),
            sample_count=int(payload["sample_count"]),
            minimum_required_sample_count=int(payload["minimum_required_sample_count"]),
            artifact_bundle=EvaluationArtifactBundle.from_dict(
                dict(payload["artifact_bundle"])
            ),
        )


@dataclass(frozen=True)
class LockboxEvidence:
    finalist_count: int
    finalist_cap: int
    access_log_ids: tuple[str, ...]
    contamination_incident_ids: tuple[str, ...]
    contamination_review_reference_ids: tuple[str, ...]
    artifact_bundle: EvaluationArtifactBundle

    def to_dict(self) -> dict[str, Any]:
        return {
            "finalist_count": self.finalist_count,
            "finalist_cap": self.finalist_cap,
            "access_log_ids": list(self.access_log_ids),
            "contamination_incident_ids": list(self.contamination_incident_ids),
            "contamination_review_reference_ids": list(
                self.contamination_review_reference_ids
            ),
            "artifact_bundle": self.artifact_bundle.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LockboxEvidence":
        return cls(
            finalist_count=int(payload["finalist_count"]),
            finalist_cap=int(payload["finalist_cap"]),
            access_log_ids=tuple(str(item) for item in payload["access_log_ids"]),
            contamination_incident_ids=tuple(
                str(item) for item in payload["contamination_incident_ids"]
            ),
            contamination_review_reference_ids=tuple(
                str(item) for item in payload["contamination_review_reference_ids"]
            ),
            artifact_bundle=EvaluationArtifactBundle.from_dict(
                dict(payload["artifact_bundle"])
            ),
        )


@dataclass(frozen=True)
class CandidateFreezeEvidence:
    freeze_ready: bool
    frozen_candidate_id: str | None
    dependency_manifest_id: str | None
    artifact_bundle: EvaluationArtifactBundle

    def to_dict(self) -> dict[str, Any]:
        return {
            "freeze_ready": self.freeze_ready,
            "frozen_candidate_id": self.frozen_candidate_id,
            "dependency_manifest_id": self.dependency_manifest_id,
            "artifact_bundle": self.artifact_bundle.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CandidateFreezeEvidence":
        return cls(
            freeze_ready=bool(payload["freeze_ready"]),
            frozen_candidate_id=(
                str(payload["frozen_candidate_id"])
                if payload.get("frozen_candidate_id") not in (None, "")
                else None
            ),
            dependency_manifest_id=(
                str(payload["dependency_manifest_id"])
                if payload.get("dependency_manifest_id") not in (None, "")
                else None
            ),
            artifact_bundle=EvaluationArtifactBundle.from_dict(
                dict(payload["artifact_bundle"])
            ),
        )


@dataclass(frozen=True)
class EvaluationProtocolRequest:
    case_id: str
    family_id: str
    subfamily_id: str
    continuation_decision_id: str
    requested_deep_tuning: bool
    stage_records: tuple[EvaluationStageRecord, ...]
    walk_forward_folds: tuple[WalkForwardFoldEvidence, ...]
    parameter_stability_checks: tuple[ParameterStabilityEvidence, ...]
    bootstrap_intervals: tuple[BootstrapIntervalEvidence, ...]
    omission_checks: tuple[OmissionCheckEvidence, ...]
    power_analysis: PowerAnalysisEvidence
    lockbox_evidence: LockboxEvidence
    candidate_freeze_evidence: CandidateFreezeEvidence
    operator_reason_bundle: tuple[str, ...]
    schema_version: int = SUPPORTED_EVALUATION_PROTOCOL_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "family_id": self.family_id,
            "subfamily_id": self.subfamily_id,
            "continuation_decision_id": self.continuation_decision_id,
            "requested_deep_tuning": self.requested_deep_tuning,
            "stage_records": [item.to_dict() for item in self.stage_records],
            "walk_forward_folds": [item.to_dict() for item in self.walk_forward_folds],
            "parameter_stability_checks": [
                item.to_dict() for item in self.parameter_stability_checks
            ],
            "bootstrap_intervals": [
                item.to_dict() for item in self.bootstrap_intervals
            ],
            "omission_checks": [item.to_dict() for item in self.omission_checks],
            "power_analysis": self.power_analysis.to_dict(),
            "lockbox_evidence": self.lockbox_evidence.to_dict(),
            "candidate_freeze_evidence": self.candidate_freeze_evidence.to_dict(),
            "operator_reason_bundle": list(self.operator_reason_bundle),
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationProtocolRequest":
        return cls(
            case_id=str(payload["case_id"]),
            family_id=str(payload["family_id"]),
            subfamily_id=str(payload["subfamily_id"]),
            continuation_decision_id=str(payload["continuation_decision_id"]),
            requested_deep_tuning=bool(payload["requested_deep_tuning"]),
            stage_records=tuple(
                EvaluationStageRecord.from_dict(dict(item))
                for item in payload["stage_records"]
            ),
            walk_forward_folds=tuple(
                WalkForwardFoldEvidence.from_dict(dict(item))
                for item in payload["walk_forward_folds"]
            ),
            parameter_stability_checks=tuple(
                ParameterStabilityEvidence.from_dict(dict(item))
                for item in payload["parameter_stability_checks"]
            ),
            bootstrap_intervals=tuple(
                BootstrapIntervalEvidence.from_dict(dict(item))
                for item in payload["bootstrap_intervals"]
            ),
            omission_checks=tuple(
                OmissionCheckEvidence.from_dict(dict(item))
                for item in payload["omission_checks"]
            ),
            power_analysis=PowerAnalysisEvidence.from_dict(
                dict(payload["power_analysis"])
            ),
            lockbox_evidence=LockboxEvidence.from_dict(dict(payload["lockbox_evidence"])),
            candidate_freeze_evidence=CandidateFreezeEvidence.from_dict(
                dict(payload["candidate_freeze_evidence"])
            ),
            operator_reason_bundle=tuple(
                str(item) for item in payload["operator_reason_bundle"]
            ),
            schema_version=int(
                payload.get(
                    "schema_version", SUPPORTED_EVALUATION_PROTOCOL_SCHEMA_VERSION
                )
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "EvaluationProtocolRequest":
        return cls.from_dict(
            _decode_json_object(payload, label="evaluation_protocol_request")
        )


@dataclass(frozen=True)
class EvaluationProtocolCheckResult:
    check_id: str
    check_name: str
    passed: bool
    status: str
    reason_code: str
    diagnostic: str
    evidence: dict[str, Any]
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationProtocolCheckResult":
        return cls(
            check_id=str(payload["check_id"]),
            check_name=str(payload["check_name"]),
            passed=bool(payload["passed"]),
            status=str(payload["status"]),
            reason_code=str(payload["reason_code"]),
            diagnostic=str(payload["diagnostic"]),
            evidence=dict(payload["evidence"]),
            remediation=str(payload["remediation"]),
        )


@dataclass(frozen=True)
class EvaluationProtocolReport:
    case_id: str
    status: str
    decision: str
    reason_code: str
    passed_count: int
    failed_count: int
    triggered_check_ids: tuple[str, ...]
    completed_stage_order: tuple[str, ...]
    omission_dimensions_covered: tuple[str, ...]
    deep_tuning_allowed: bool
    candidate_freeze_ready: bool
    check_results: tuple[EvaluationProtocolCheckResult, ...]
    retained_artifact_ids: tuple[str, ...]
    correlation_ids: tuple[str, ...]
    operator_reason_bundle: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["check_results"] = [item.to_dict() for item in self.check_results]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationProtocolReport":
        return cls(
            case_id=str(payload["case_id"]),
            status=str(payload["status"]),
            decision=str(payload["decision"]),
            reason_code=str(payload["reason_code"]),
            passed_count=int(payload["passed_count"]),
            failed_count=int(payload["failed_count"]),
            triggered_check_ids=tuple(str(item) for item in payload["triggered_check_ids"]),
            completed_stage_order=tuple(str(item) for item in payload["completed_stage_order"]),
            omission_dimensions_covered=tuple(
                str(item) for item in payload["omission_dimensions_covered"]
            ),
            deep_tuning_allowed=bool(payload["deep_tuning_allowed"]),
            candidate_freeze_ready=bool(payload["candidate_freeze_ready"]),
            check_results=tuple(
                EvaluationProtocolCheckResult.from_dict(dict(item))
                for item in payload["check_results"]
            ),
            retained_artifact_ids=tuple(
                str(item) for item in payload["retained_artifact_ids"]
            ),
            correlation_ids=tuple(str(item) for item in payload["correlation_ids"]),
            operator_reason_bundle=tuple(
                str(item) for item in payload["operator_reason_bundle"]
            ),
            explanation=str(payload["explanation"]),
            remediation=str(payload["remediation"]),
            timestamp=str(payload.get("timestamp", _utcnow())),
        )

    @classmethod
    def from_json(cls, payload: str) -> "EvaluationProtocolReport":
        return cls.from_dict(
            _decode_json_object(payload, label="evaluation_protocol_report")
        )


def _artifact_bundle_complete(bundle: EvaluationArtifactBundle) -> bool:
    return bool(
        bundle.artifact_manifest_id
        and bundle.retained_log_ids
        and bundle.correlation_ids
        and bundle.expected_actual_diff_ids
        and bundle.operator_reason_bundle
    )


def _collect_bundles(request: EvaluationProtocolRequest) -> tuple[EvaluationArtifactBundle, ...]:
    bundles: list[EvaluationArtifactBundle] = [
        stage.artifact_bundle for stage in request.stage_records
    ]
    bundles.extend(fold.artifact_bundle for fold in request.walk_forward_folds)
    bundles.extend(
        check.artifact_bundle for check in request.parameter_stability_checks
    )
    bundles.extend(
        interval.artifact_bundle for interval in request.bootstrap_intervals
    )
    bundles.extend(check.artifact_bundle for check in request.omission_checks)
    bundles.append(request.power_analysis.artifact_bundle)
    bundles.append(request.lockbox_evidence.artifact_bundle)
    bundles.append(request.candidate_freeze_evidence.artifact_bundle)
    return tuple(bundles)


def _retained_artifact_ids(request: EvaluationProtocolRequest) -> tuple[str, ...]:
    artifact_ids: list[str] = []
    for bundle in _collect_bundles(request):
        artifact_ids.append(bundle.artifact_manifest_id)
        artifact_ids.extend(bundle.retained_log_ids)
        artifact_ids.extend(bundle.expected_actual_diff_ids)
    artifact_ids.extend(request.lockbox_evidence.access_log_ids)
    artifact_ids.extend(request.lockbox_evidence.contamination_review_reference_ids)
    if request.candidate_freeze_evidence.frozen_candidate_id is not None:
        artifact_ids.append(request.candidate_freeze_evidence.frozen_candidate_id)
    if request.candidate_freeze_evidence.dependency_manifest_id is not None:
        artifact_ids.append(request.candidate_freeze_evidence.dependency_manifest_id)
    return _sorted_unique(tuple(artifact_ids))


def _correlation_ids(request: EvaluationProtocolRequest) -> tuple[str, ...]:
    values: list[str] = []
    for bundle in _collect_bundles(request):
        values.extend(bundle.correlation_ids)
    return _sorted_unique(tuple(values))


def _check(
    *,
    check_id: str,
    check_name: str,
    passed: bool,
    reason_code: str,
    diagnostic: str,
    evidence: dict[str, Any],
    remediation: str,
) -> EvaluationProtocolCheckResult:
    return EvaluationProtocolCheckResult(
        check_id=check_id,
        check_name=check_name,
        passed=passed,
        status=(
            EvaluationProtocolStatus.PASS.value
            if passed
            else EvaluationProtocolStatus.VIOLATION.value
        ),
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence=_jsonable(evidence),
        remediation=remediation,
    )


def validate_evaluation_protocol_contract() -> list[str]:
    errors: list[str] = []
    if SUPPORTED_EVALUATION_PROTOCOL_SCHEMA_VERSION < 1:
        errors.append("schema version must remain positive")
    if len(REQUIRED_EVALUATION_STAGE_ORDER) != len(set(REQUIRED_EVALUATION_STAGE_ORDER)):
        errors.append("required evaluation stage order must be unique")
    if len(REQUIRED_OMISSION_DIMENSIONS) != len(set(REQUIRED_OMISSION_DIMENSIONS)):
        errors.append("required omission dimensions must be unique")
    if len(EVALUATION_PROTOCOL_CHECK_IDS) != len(set(EVALUATION_PROTOCOL_CHECK_IDS)):
        errors.append("evaluation protocol check ids must be unique")
    return errors


VALIDATION_ERRORS = validate_evaluation_protocol_contract()


def _validate_request(request: EvaluationProtocolRequest) -> list[str]:
    errors: list[str] = []
    if request.schema_version != SUPPORTED_EVALUATION_PROTOCOL_SCHEMA_VERSION:
        errors.append("unsupported schema version")
    if not request.case_id:
        errors.append("case_id must be non-empty")
    if not request.family_id:
        errors.append("family_id must be non-empty")
    if not request.subfamily_id:
        errors.append("subfamily_id must be non-empty")
    if not request.continuation_decision_id:
        errors.append("continuation_decision_id must be non-empty")
    if not request.operator_reason_bundle:
        errors.append("operator_reason_bundle must be non-empty")

    stage_ids = [item.stage.value for item in request.stage_records]
    if len(stage_ids) != len(set(stage_ids)):
        errors.append("stage_records must not repeat stages")

    for fold in request.walk_forward_folds:
        if not fold.fold_id or not fold.training_window_id or not fold.validation_window_id:
            errors.append("walk-forward folds require fold/training/validation identifiers")
        if not fold.parameter_set_id:
            errors.append("walk-forward folds require parameter_set_id")

    for check in request.parameter_stability_checks:
        if not check.parameter_id:
            errors.append("parameter stability checks require parameter_id")
        if check.allowed_stability_ratio <= 0:
            errors.append("allowed_stability_ratio must be positive")
        if check.stability_ratio < 0:
            errors.append("stability_ratio must be non-negative")

    for interval in request.bootstrap_intervals:
        if not interval.metric_id:
            errors.append("bootstrap intervals require metric_id")
        if interval.block_length_bars <= 0:
            errors.append("block_length_bars must be positive")
        if interval.resample_count <= 0:
            errors.append("resample_count must be positive")
        if not 0 < interval.confidence_level < 1:
            errors.append("confidence_level must be within (0, 1)")
        if interval.upper_bound < interval.lower_bound:
            errors.append("bootstrap bounds must be ordered")

    for check in request.omission_checks:
        if not check.omitted_slice_id:
            errors.append("omission checks require omitted_slice_id")

    if not request.power_analysis.metric_id:
        errors.append("power_analysis.metric_id must be non-empty")
    if request.power_analysis.minimum_detectable_edge_bps < 0:
        errors.append("minimum_detectable_edge_bps must be non-negative")
    if not 0 < request.power_analysis.minimum_required_power <= 1:
        errors.append("minimum_required_power must be within (0, 1]")
    if not 0 < request.power_analysis.power <= 1:
        errors.append("power must be within (0, 1]")
    if request.power_analysis.sample_count <= 0:
        errors.append("sample_count must be positive")
    if request.power_analysis.minimum_required_sample_count <= 0:
        errors.append("minimum_required_sample_count must be positive")

    if request.lockbox_evidence.finalist_cap <= 0:
        errors.append("lockbox finalist_cap must be positive")
    if request.lockbox_evidence.finalist_count < 0:
        errors.append("lockbox finalist_count must be non-negative")

    for bundle in _collect_bundles(request):
        if not bundle.artifact_manifest_id:
            errors.append("artifact bundles require artifact_manifest_id")

    return errors


def _invalid_report(
    request: EvaluationProtocolRequest,
    errors: list[str],
) -> EvaluationProtocolReport:
    retained_artifacts = _retained_artifact_ids(request)
    correlation_ids = _correlation_ids(request)
    return EvaluationProtocolReport(
        case_id=request.case_id,
        status=EvaluationProtocolStatus.INVALID.value,
        decision=EvaluationProtocolDecision.REPAIR_PROTOCOL.value,
        reason_code="EVALUATION_PROTOCOL_REQUEST_INVALID",
        passed_count=0,
        failed_count=0,
        triggered_check_ids=(),
        completed_stage_order=tuple(
            stage.stage.value for stage in request.stage_records if stage.completed
        ),
        omission_dimensions_covered=_sorted_unique(
            tuple(check.omission_dimension.value for check in request.omission_checks)
        ),
        deep_tuning_allowed=False,
        candidate_freeze_ready=False,
        check_results=(),
        retained_artifact_ids=retained_artifacts,
        correlation_ids=correlation_ids,
        operator_reason_bundle=request.operator_reason_bundle,
        explanation=(
            "The evaluation-protocol request is malformed and cannot be used to decide "
            f"deep tuning or candidate freeze: {errors}."
        ),
        remediation="Repair the request schema, identifiers, and thresholds before evaluation.",
    )


def _stage_hierarchy_check(
    request: EvaluationProtocolRequest,
) -> EvaluationProtocolCheckResult:
    actual_order = tuple(record.stage.value for record in request.stage_records)
    completed_order = tuple(record.stage.value for record in request.stage_records if record.completed)
    prefix = REQUIRED_EVALUATION_STAGE_ORDER[: len(completed_order)]
    passed = actual_order == REQUIRED_EVALUATION_STAGE_ORDER and completed_order == prefix
    return _check(
        check_id="EP01",
        check_name="explicit_stage_hierarchy",
        passed=passed,
        reason_code=(
            "EVALUATION_PROTOCOL_STAGE_HIERARCHY_VALID"
            if passed
            else "EVALUATION_PROTOCOL_STAGE_HIERARCHY_BROKEN"
        ),
        diagnostic=(
            "The evaluation path is explicit and completed stages remain an ordered prefix "
            "from screening through candidate freeze."
            if passed
            else "Stage records must preserve the canonical order and completed stages must not skip ahead."
        ),
        evidence={
            "required_stage_order": list(REQUIRED_EVALUATION_STAGE_ORDER),
            "actual_stage_order": list(actual_order),
            "completed_stage_order": list(completed_order),
        },
        remediation="Repair the stage ordering so screening, validation, stress, omission, lockbox, and candidate freeze remain explicit.",
    )


def _artifact_retention_check(
    request: EvaluationProtocolRequest,
) -> EvaluationProtocolCheckResult:
    missing: dict[str, list[str]] = {}
    for record in request.stage_records:
        bundle = record.artifact_bundle
        absent: list[str] = []
        if not bundle.artifact_manifest_id:
            absent.append("artifact_manifest_id")
        if not bundle.retained_log_ids:
            absent.append("retained_log_ids")
        if not bundle.correlation_ids:
            absent.append("correlation_ids")
        if not bundle.expected_actual_diff_ids:
            absent.append("expected_actual_diff_ids")
        if not bundle.operator_reason_bundle:
            absent.append("operator_reason_bundle")
        if absent:
            missing[record.stage.value] = absent

    passed = not missing and bool(request.operator_reason_bundle)
    return _check(
        check_id="EP02",
        check_name="retained_artifacts_and_reason_bundles",
        passed=passed,
        reason_code=(
            "EVALUATION_PROTOCOL_ARTIFACT_RETENTION_VALID"
            if passed
            else "EVALUATION_PROTOCOL_ARTIFACT_RETENTION_INCOMPLETE"
        ),
        diagnostic=(
            "Each stage retains logs, correlation ids, expected-vs-actual diffs, manifests, and operator-readable reasons."
            if passed
            else "Every stage must retain enough artifacts to explain why a candidate advanced, stalled, or failed."
        ),
        evidence={
            "missing_by_stage": missing,
            "operator_reason_bundle": list(request.operator_reason_bundle),
        },
        remediation="Retain per-stage manifests, logs, diffs, and reason bundles instead of only the final decision.",
    )


def _walk_forward_check(
    request: EvaluationProtocolRequest,
) -> EvaluationProtocolCheckResult:
    fold_ids = [fold.fold_id for fold in request.walk_forward_folds]
    duplicate_ids = sorted(fold_id for fold_id in set(fold_ids) if fold_ids.count(fold_id) > 1)
    incomplete_folds = [
        fold.fold_id
        for fold in request.walk_forward_folds
        if not fold.passed or not _artifact_bundle_complete(fold.artifact_bundle)
    ]
    passed = (
        len(request.walk_forward_folds) >= 2
        and not duplicate_ids
        and not incomplete_folds
    )
    return _check(
        check_id="EP03",
        check_name="walk_forward_folds",
        passed=passed,
        reason_code=(
            "EVALUATION_PROTOCOL_WALK_FORWARD_VALID"
            if passed
            else "EVALUATION_PROTOCOL_WALK_FORWARD_INCOMPLETE"
        ),
        diagnostic=(
            "Multiple walk-forward folds passed with retained evidence."
            if passed
            else "Promotion-grade evaluation requires multiple passed walk-forward folds with retained artifacts."
        ),
        evidence={
            "fold_count": len(request.walk_forward_folds),
            "duplicate_fold_ids": duplicate_ids,
            "incomplete_fold_ids": incomplete_folds,
        },
        remediation="Run at least two distinct walk-forward folds and retain the fold manifests and diffs.",
    )


def _parameter_stability_check(
    request: EvaluationProtocolRequest,
) -> EvaluationProtocolCheckResult:
    unstable_parameters = [
        check.parameter_id
        for check in request.parameter_stability_checks
        if (
            not check.passed
            or check.stability_ratio > check.allowed_stability_ratio
            or not _artifact_bundle_complete(check.artifact_bundle)
        )
    ]
    passed = bool(request.parameter_stability_checks) and not unstable_parameters
    return _check(
        check_id="EP04",
        check_name="parameter_stability",
        passed=passed,
        reason_code=(
            "EVALUATION_PROTOCOL_PARAMETER_STABILITY_VALID"
            if passed
            else "EVALUATION_PROTOCOL_PARAMETER_STABILITY_FAILED"
        ),
        diagnostic=(
            "Parameter perturbation checks stayed inside the admissible stability envelope."
            if passed
            else "Parameter stability checks failed or were not retained for every promotable dimension."
        ),
        evidence={
            "checked_parameter_ids": [
                check.parameter_id for check in request.parameter_stability_checks
            ],
            "unstable_parameter_ids": unstable_parameters,
        },
        remediation="Retain parameter perturbation results and reject regions that degrade outside the allowed stability band.",
    )


def _bootstrap_check(
    request: EvaluationProtocolRequest,
) -> EvaluationProtocolCheckResult:
    invalid_metrics = [
        interval.metric_id
        for interval in request.bootstrap_intervals
        if (
            not interval.passed
            or interval.block_length_bars <= 0
            or interval.resample_count <= 0
            or interval.upper_bound < interval.lower_bound
            or not _artifact_bundle_complete(interval.artifact_bundle)
        )
    ]
    passed = bool(request.bootstrap_intervals) and not invalid_metrics
    return _check(
        check_id="EP05",
        check_name="block_bootstrap_confidence_intervals",
        passed=passed,
        reason_code=(
            "EVALUATION_PROTOCOL_BLOCK_BOOTSTRAP_VALID"
            if passed
            else "EVALUATION_PROTOCOL_BLOCK_BOOTSTRAP_MISSING"
        ),
        diagnostic=(
            "Block-bootstrap confidence intervals are retained for the promotable metrics."
            if passed
            else "Promotion-grade evaluation requires valid block-bootstrap intervals with retained artifacts."
        ),
        evidence={
            "metric_ids": [interval.metric_id for interval in request.bootstrap_intervals],
            "invalid_metric_ids": invalid_metrics,
        },
        remediation="Retain block-bootstrap intervals for the promotable metrics and repair incomplete interval evidence.",
    )


def _omission_check(
    request: EvaluationProtocolRequest,
) -> EvaluationProtocolCheckResult:
    covered = _sorted_unique(
        tuple(check.omission_dimension.value for check in request.omission_checks)
    )
    missing_dimensions = sorted(
        set(REQUIRED_OMISSION_DIMENSIONS).difference(set(covered))
    )
    failed_dimensions = [
        check.omission_dimension.value
        for check in request.omission_checks
        if not check.passed or not _artifact_bundle_complete(check.artifact_bundle)
    ]
    passed = not missing_dimensions and not failed_dimensions
    return _check(
        check_id="EP06",
        check_name="omission_matrix",
        passed=passed,
        reason_code=(
            "EVALUATION_PROTOCOL_OMISSION_COVERAGE_VALID"
            if passed
            else "EVALUATION_PROTOCOL_OMISSION_COVERAGE_MISSING"
        ),
        diagnostic=(
            "Regime, segment, anchor, and event-cluster omission checks all passed with retained evidence."
            if passed
            else "Omission coverage is incomplete or failing for one or more required omission dimensions."
        ),
        evidence={
            "required_dimensions": list(REQUIRED_OMISSION_DIMENSIONS),
            "covered_dimensions": list(covered),
            "missing_dimensions": missing_dimensions,
            "failed_dimensions": failed_dimensions,
        },
        remediation="Run regime, segment, anchor, and event-cluster omission checks and keep the resulting evidence manifests.",
    )


def _power_analysis_check(
    request: EvaluationProtocolRequest,
) -> EvaluationProtocolCheckResult:
    analysis = request.power_analysis
    artifact_complete = _artifact_bundle_complete(analysis.artifact_bundle)
    analysis_recorded = bool(analysis.metric_id) and artifact_complete
    deep_tuning_allowed = analysis.approved_for_deep_tuning
    passed = analysis_recorded and (
        not request.requested_deep_tuning or deep_tuning_allowed
    )
    reason_code = "EVALUATION_PROTOCOL_POWER_RECORDED"
    if request.requested_deep_tuning and not deep_tuning_allowed:
        reason_code = "EVALUATION_PROTOCOL_POWER_INSUFFICIENT"
    elif not analysis_recorded:
        reason_code = "EVALUATION_PROTOCOL_POWER_MISSING"
    return _check(
        check_id="EP07",
        check_name="power_analysis_before_deep_tuning",
        passed=passed,
        reason_code=reason_code,
        diagnostic=(
            "Power analysis is retained and the estimated edge is detectable before deep tuning."
            if passed
            else "Deep tuning is blocked until power analysis shows a detectable edge with adequate sample size."
        ),
        evidence={
            "requested_deep_tuning": request.requested_deep_tuning,
            "metric_id": analysis.metric_id,
            "estimated_edge_bps": analysis.estimated_edge_bps,
            "minimum_detectable_edge_bps": analysis.minimum_detectable_edge_bps,
            "power": analysis.power,
            "minimum_required_power": analysis.minimum_required_power,
            "sample_count": analysis.sample_count,
            "minimum_required_sample_count": analysis.minimum_required_sample_count,
            "approved_for_deep_tuning": deep_tuning_allowed,
        },
        remediation="Record power analysis before deep tuning and stop tuning when the edge is not detectably above noise.",
    )


def _lockbox_check(
    request: EvaluationProtocolRequest,
) -> EvaluationProtocolCheckResult:
    evidence = request.lockbox_evidence
    contamination_requires_review = bool(evidence.contamination_incident_ids)
    contamination_documented = (
        not contamination_requires_review
        or bool(evidence.contamination_review_reference_ids)
    )
    passed = (
        evidence.finalist_count > 0
        and evidence.finalist_count <= evidence.finalist_cap
        and bool(evidence.access_log_ids)
        and contamination_documented
        and _artifact_bundle_complete(evidence.artifact_bundle)
    )
    return _check(
        check_id="EP08",
        check_name="lockbox_readiness",
        passed=passed,
        reason_code=(
            "EVALUATION_PROTOCOL_LOCKBOX_READY"
            if passed
            else "EVALUATION_PROTOCOL_LOCKBOX_CONTROLS_INCOMPLETE"
        ),
        diagnostic=(
            "Lockbox entry remains bounded, logged, and explainable."
            if passed
            else "Lockbox evidence must retain access logs, finalist bounds, and incident references when contamination occurs."
        ),
        evidence={
            "finalist_count": evidence.finalist_count,
            "finalist_cap": evidence.finalist_cap,
            "access_log_ids": list(evidence.access_log_ids),
            "contamination_incident_ids": list(evidence.contamination_incident_ids),
            "contamination_review_reference_ids": list(
                evidence.contamination_review_reference_ids
            ),
        },
        remediation="Bound lockbox finalist count, retain access logs, and record review references for any contamination incident.",
    )


def _candidate_freeze_check(
    request: EvaluationProtocolRequest,
    prerequisite_checks: tuple[EvaluationProtocolCheckResult, ...],
) -> EvaluationProtocolCheckResult:
    evidence = request.candidate_freeze_evidence
    prerequisites_passed = all(check.passed for check in prerequisite_checks)
    freeze_ready = bool(
        evidence.freeze_ready
        and evidence.frozen_candidate_id
        and evidence.dependency_manifest_id
        and _artifact_bundle_complete(evidence.artifact_bundle)
    )
    passed = prerequisites_passed and freeze_ready
    return _check(
        check_id="EP09",
        check_name="candidate_freeze_gate",
        passed=passed,
        reason_code=(
            "EVALUATION_PROTOCOL_CANDIDATE_FREEZE_READY"
            if passed
            else "EVALUATION_PROTOCOL_CANDIDATE_FREEZE_BLOCKED"
        ),
        diagnostic=(
            "The candidate can be frozen because the protocol prerequisites passed and the freeze bundle is explicit."
            if passed
            else "Candidate freeze stays blocked until robustness, omission, power, and lockbox prerequisites all pass."
        ),
        evidence={
            "prerequisite_check_ids": [check.check_id for check in prerequisite_checks],
            "prerequisites_passed": prerequisites_passed,
            "freeze_ready": evidence.freeze_ready,
            "frozen_candidate_id": evidence.frozen_candidate_id,
            "dependency_manifest_id": evidence.dependency_manifest_id,
        },
        remediation="Repair the failed robustness prerequisites or complete the explicit freeze bundle before candidate freeze.",
    )


def _build_explanation(
    checks: tuple[EvaluationProtocolCheckResult, ...],
) -> str:
    failing_ids = {check.check_id for check in checks if not check.passed}
    if not failing_ids:
        return (
            "The evaluation hierarchy is explicit, robustness work is retained, omission coverage is complete, "
            "deep tuning is power-justified, and the candidate is ready for freeze."
        )

    segments: list[str] = []
    if "EP01" in failing_ids:
        segments.append("The stage hierarchy is not preserved from screening through candidate freeze.")
    if "EP02" in failing_ids:
        segments.append("Intermediate artifacts are incomplete, so rejections or promotions would not be explainable later.")
    if "EP03" in failing_ids:
        segments.append("Walk-forward coverage is incomplete.")
    if "EP04" in failing_ids:
        segments.append("Parameter stability is not yet defensible.")
    if "EP05" in failing_ids:
        segments.append("Block-bootstrap confidence intervals are missing or invalid.")
    if "EP06" in failing_ids:
        segments.append("Required omission dimensions are missing or failing.")
    if "EP07" in failing_ids:
        segments.append("Power analysis does not justify deeper tuning yet.")
    if "EP08" in failing_ids:
        segments.append("Lockbox entry evidence is incomplete.")
    if "EP09" in failing_ids:
        segments.append("Candidate freeze remains blocked.")
    return " ".join(segments)


def evaluate_evaluation_protocol(
    request: EvaluationProtocolRequest,
) -> EvaluationProtocolReport:
    request_errors = _validate_request(request)
    if request_errors:
        return _invalid_report(request, request_errors)

    checks_without_freeze = (
        _stage_hierarchy_check(request),
        _artifact_retention_check(request),
        _walk_forward_check(request),
        _parameter_stability_check(request),
        _bootstrap_check(request),
        _omission_check(request),
        _power_analysis_check(request),
        _lockbox_check(request),
    )
    freeze_check = _candidate_freeze_check(request, checks_without_freeze)
    checks = checks_without_freeze + (freeze_check,)

    failing_checks = tuple(check for check in checks if not check.passed)
    passed_count = sum(1 for check in checks if check.passed)
    failed_count = len(checks) - passed_count
    status = (
        EvaluationProtocolStatus.PASS.value
        if not failing_checks
        else EvaluationProtocolStatus.VIOLATION.value
    )
    decision = (
        EvaluationProtocolDecision.FREEZE_CANDIDATE.value
        if not failing_checks
        else EvaluationProtocolDecision.HOLD.value
    )
    reason_code = (
        "EVALUATION_PROTOCOL_READY"
        if not failing_checks
        else failing_checks[0].reason_code
    )
    explanation = _build_explanation(checks)
    remediation = (
        "No remediation required."
        if not failing_checks
        else failing_checks[0].remediation
    )

    return EvaluationProtocolReport(
        case_id=request.case_id,
        status=status,
        decision=decision,
        reason_code=reason_code,
        passed_count=passed_count,
        failed_count=failed_count,
        triggered_check_ids=tuple(check.check_id for check in failing_checks),
        completed_stage_order=tuple(
            stage.stage.value for stage in request.stage_records if stage.completed
        ),
        omission_dimensions_covered=_sorted_unique(
            tuple(check.omission_dimension.value for check in request.omission_checks)
        ),
        deep_tuning_allowed=request.power_analysis.approved_for_deep_tuning,
        candidate_freeze_ready=freeze_check.passed,
        check_results=checks,
        retained_artifact_ids=_retained_artifact_ids(request),
        correlation_ids=_correlation_ids(request),
        operator_reason_bundle=request.operator_reason_bundle,
        explanation=explanation,
        remediation=remediation,
    )
