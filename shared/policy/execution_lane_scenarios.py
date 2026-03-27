"""Execution-lane vertical-slice and calibration scenario suites.

This module composes the existing lane, portability, and calibration contracts
into operator-readable scenario reports with correlated logs and retained
artifact manifests. It is the scripted verification surface for bead 11.9.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any

from shared.policy.posture import validate_full_posture
from shared.policy.product_profiles import ProductLane, product_profiles_by_id
from shared.policy.viability_gate import (
    ExecutionSymbolDimensionResult,
    FidelityCalibrationDimensionResult,
    GateOutcome,
    PortabilityDimensionResult,
    evaluate_execution_symbol_first_viability_screen,
    evaluate_fidelity_calibration,
    evaluate_portability_and_native_validation,
    evaluate_viability_gate,
)

SCENARIO_REPORT_SCHEMA_VERSION = 1


def _utcnow() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _decode_json_object(payload: str, *, label: str) -> dict[str, Any]:
    try:
        decoded = json.JSONDecoder().decode(payload)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must decode to an object")
    return decoded


def _sha256_payload(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@unique
class ExecutionLaneScenarioKind(str, Enum):
    VERTICAL_SLICE = "vertical_slice"
    CALIBRATION = "calibration"


@unique
class ExecutionLaneScenarioDecision(str, Enum):
    PASS = "pass"  # nosec B105 - lifecycle decision literal, not a credential
    PIVOT = "pivot"
    EXCLUDED = "excluded"
    INVALID = "invalid"


@dataclass(frozen=True)
class ScenarioTraceEntry:
    step_id: str
    step_name: str
    passed: bool
    reason_code: str
    diagnostic: str
    evidence: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactEntry:
    artifact_id: str
    artifact_role: str
    relative_path: str
    sha256: str
    content_type: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactManifest:
    manifest_id: str
    generated_at_utc: str
    retention_class: str
    contains_secrets: bool
    redaction_policy: str
    artifacts: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerticalSliceInputs:
    sentinel_strategy_route: str
    expected_sentinel_strategy_route: str
    broker_reconnect_observed: bool
    reconnect_observation_reference: str
    viability_gate_inputs: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VerticalSliceInputs":
        return cls(
            sentinel_strategy_route=str(payload["sentinel_strategy_route"]),
            expected_sentinel_strategy_route=str(payload["expected_sentinel_strategy_route"]),
            broker_reconnect_observed=bool(payload["broker_reconnect_observed"]),
            reconnect_observation_reference=str(payload["reconnect_observation_reference"]),
            viability_gate_inputs={
                str(key): bool(value)
                for key, value in dict(payload["viability_gate_inputs"]).items()
            },
        )


@dataclass(frozen=True)
class CalibrationInputs:
    research_artifact_id: str
    native_execution_history_obtained: bool
    live_or_paper_observations_obtained: bool
    execution_symbol_dimensions: tuple[ExecutionSymbolDimensionResult, ...]
    portability_study_id: str | None
    portability_dimensions: tuple[PortabilityDimensionResult, ...]
    sufficient_native_1oz_history_exists: bool
    native_1oz_validation_study_id: str | None
    native_1oz_validation_passed: bool | None
    calibration_evidence_report_id: str
    fidelity_dimensions: tuple[FidelityCalibrationDimensionResult, ...]
    decision_interval_seconds: int
    uses_bar_based_logic: bool
    uses_one_bar_late_decisions: bool
    depends_on_order_book_imbalance: bool
    requires_queue_position_edge: bool
    requires_sub_minute_market_making: bool
    requires_premium_live_depth_data: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_artifact_id": self.research_artifact_id,
            "native_execution_history_obtained": self.native_execution_history_obtained,
            "live_or_paper_observations_obtained": self.live_or_paper_observations_obtained,
            "execution_symbol_dimensions": [
                dimension.to_dict() for dimension in self.execution_symbol_dimensions
            ],
            "portability_study_id": self.portability_study_id,
            "portability_dimensions": [
                dimension.to_dict() for dimension in self.portability_dimensions
            ],
            "sufficient_native_1oz_history_exists": self.sufficient_native_1oz_history_exists,
            "native_1oz_validation_study_id": self.native_1oz_validation_study_id,
            "native_1oz_validation_passed": self.native_1oz_validation_passed,
            "calibration_evidence_report_id": self.calibration_evidence_report_id,
            "fidelity_dimensions": [
                dimension.to_dict() for dimension in self.fidelity_dimensions
            ],
            "decision_interval_seconds": self.decision_interval_seconds,
            "uses_bar_based_logic": self.uses_bar_based_logic,
            "uses_one_bar_late_decisions": self.uses_one_bar_late_decisions,
            "depends_on_order_book_imbalance": self.depends_on_order_book_imbalance,
            "requires_queue_position_edge": self.requires_queue_position_edge,
            "requires_sub_minute_market_making": self.requires_sub_minute_market_making,
            "requires_premium_live_depth_data": self.requires_premium_live_depth_data,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CalibrationInputs":
        return cls(
            research_artifact_id=str(payload["research_artifact_id"]),
            native_execution_history_obtained=bool(payload["native_execution_history_obtained"]),
            live_or_paper_observations_obtained=bool(payload["live_or_paper_observations_obtained"]),
            execution_symbol_dimensions=tuple(
                ExecutionSymbolDimensionResult(**dict(item))
                for item in list(payload["execution_symbol_dimensions"])
            ),
            portability_study_id=(
                str(payload["portability_study_id"])
                if payload.get("portability_study_id") is not None
                else None
            ),
            portability_dimensions=tuple(
                PortabilityDimensionResult(**dict(item))
                for item in list(payload["portability_dimensions"])
            ),
            sufficient_native_1oz_history_exists=bool(
                payload["sufficient_native_1oz_history_exists"]
            ),
            native_1oz_validation_study_id=(
                str(payload["native_1oz_validation_study_id"])
                if payload.get("native_1oz_validation_study_id") is not None
                else None
            ),
            native_1oz_validation_passed=(
                bool(payload["native_1oz_validation_passed"])
                if payload.get("native_1oz_validation_passed") is not None
                else None
            ),
            calibration_evidence_report_id=str(payload["calibration_evidence_report_id"]),
            fidelity_dimensions=tuple(
                FidelityCalibrationDimensionResult(**dict(item))
                for item in list(payload["fidelity_dimensions"])
            ),
            decision_interval_seconds=int(payload["decision_interval_seconds"]),
            uses_bar_based_logic=bool(payload["uses_bar_based_logic"]),
            uses_one_bar_late_decisions=bool(payload["uses_one_bar_late_decisions"]),
            depends_on_order_book_imbalance=bool(payload["depends_on_order_book_imbalance"]),
            requires_queue_position_edge=bool(payload["requires_queue_position_edge"]),
            requires_sub_minute_market_making=bool(payload["requires_sub_minute_market_making"]),
            requires_premium_live_depth_data=bool(payload["requires_premium_live_depth_data"]),
        )


@dataclass(frozen=True)
class ExecutionLaneScenarioRequest:
    case_id: str
    scenario_kind: str
    run_id: str
    correlation_id: str
    decision_trace_id: str
    candidate_id: str
    strategy_class_id: str
    research_symbol: str
    execution_symbol: str
    route_broker: str
    route_lane: str
    product_profile_id: str
    account_value_usd: int
    live_contracts: int
    decision_interval_seconds: int
    active_bundles: int
    deployment_hosts: int
    preserved_input_artifact_ids: tuple[str, ...]
    supporting_data_refs: tuple[str, ...]
    vertical_slice: VerticalSliceInputs | None = None
    calibration: CalibrationInputs | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "scenario_kind": self.scenario_kind,
            "run_id": self.run_id,
            "correlation_id": self.correlation_id,
            "decision_trace_id": self.decision_trace_id,
            "candidate_id": self.candidate_id,
            "strategy_class_id": self.strategy_class_id,
            "research_symbol": self.research_symbol,
            "execution_symbol": self.execution_symbol,
            "route_broker": self.route_broker,
            "route_lane": self.route_lane,
            "product_profile_id": self.product_profile_id,
            "account_value_usd": self.account_value_usd,
            "live_contracts": self.live_contracts,
            "decision_interval_seconds": self.decision_interval_seconds,
            "active_bundles": self.active_bundles,
            "deployment_hosts": self.deployment_hosts,
            "preserved_input_artifact_ids": list(self.preserved_input_artifact_ids),
            "supporting_data_refs": list(self.supporting_data_refs),
            "vertical_slice": self.vertical_slice.to_dict() if self.vertical_slice else None,
            "calibration": self.calibration.to_dict() if self.calibration else None,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ExecutionLaneScenarioRequest":
        return cls(
            case_id=str(payload["case_id"]),
            scenario_kind=str(payload["scenario_kind"]),
            run_id=str(payload["run_id"]),
            correlation_id=str(payload["correlation_id"]),
            decision_trace_id=str(payload["decision_trace_id"]),
            candidate_id=str(payload["candidate_id"]),
            strategy_class_id=str(payload["strategy_class_id"]),
            research_symbol=str(payload["research_symbol"]),
            execution_symbol=str(payload["execution_symbol"]),
            route_broker=str(payload["route_broker"]),
            route_lane=str(payload["route_lane"]),
            product_profile_id=str(payload["product_profile_id"]),
            account_value_usd=int(payload["account_value_usd"]),
            live_contracts=int(payload["live_contracts"]),
            decision_interval_seconds=int(payload["decision_interval_seconds"]),
            active_bundles=int(payload["active_bundles"]),
            deployment_hosts=int(payload["deployment_hosts"]),
            preserved_input_artifact_ids=tuple(
                str(item) for item in list(payload["preserved_input_artifact_ids"])
            ),
            supporting_data_refs=tuple(
                str(item) for item in list(payload["supporting_data_refs"])
            ),
            vertical_slice=(
                VerticalSliceInputs.from_dict(dict(payload["vertical_slice"]))
                if payload.get("vertical_slice") is not None
                else None
            ),
            calibration=(
                CalibrationInputs.from_dict(dict(payload["calibration"]))
                if payload.get("calibration") is not None
                else None
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ExecutionLaneScenarioRequest":
        return cls.from_dict(_decode_json_object(payload, label="execution_lane_scenario_request"))


@dataclass(frozen=True)
class ExecutionLaneScenarioReport:
    schema_version: int
    case_id: str
    scenario_kind: str
    decision: str
    reason_code: str
    correlation_id: str
    decision_trace_id: str
    run_id: str
    candidate_id: str
    strategy_class_id: str
    product_profile_id: str
    preserved_input_artifact_ids: tuple[str, ...]
    supporting_data_refs: tuple[str, ...]
    expected_vs_actual_diffs: list[dict[str, Any]]
    operator_reason_bundle: dict[str, Any]
    artifact_manifest: dict[str, Any]
    structured_logs: list[dict[str, Any]]
    decision_trace: list[dict[str, Any]]
    vertical_slice_report: dict[str, Any] | None
    calibration_report: dict[str, Any] | None
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, payload: str) -> "ExecutionLaneScenarioReport":
        return cls(**_decode_json_object(payload, label="execution_lane_scenario_report"))


def _coerce_lane(value: str) -> ProductLane:
    return ProductLane(value)


def _stage_entry(
    *,
    step_id: str,
    step_name: str,
    passed: bool,
    reason_code: str,
    diagnostic: str,
    evidence: dict[str, Any] | None = None,
) -> ScenarioTraceEntry:
    return ScenarioTraceEntry(
        step_id=step_id,
        step_name=step_name,
        passed=passed,
        reason_code=reason_code,
        diagnostic=diagnostic,
        evidence=evidence or {},
    )


def _common_context(
    request: ExecutionLaneScenarioRequest,
) -> tuple[list[ScenarioTraceEntry], list[dict[str, Any]], dict[str, Any], bool, bool]:
    traces: list[ScenarioTraceEntry] = []
    diffs: list[dict[str, Any]] = []
    posture_results = validate_full_posture(
        research_symbol=request.research_symbol,
        execution_symbol=request.execution_symbol,
        broker=request.route_broker,
        account_value_usd=request.account_value_usd,
        live_contracts=request.live_contracts,
        decision_interval_seconds=request.decision_interval_seconds,
        active_bundles=request.active_bundles,
        deployment_hosts=request.deployment_hosts,
    )
    posture_failures = [result for result in posture_results if result.violated]
    posture_entry = _stage_entry(
        step_id="EL00",
        step_name="approved_posture_context",
        passed=not posture_failures,
        reason_code=(
            "EXECUTION_LANE_CONTEXT_POSTURE_PASS"
            if not posture_failures
            else "EXECUTION_LANE_CONTEXT_POSTURE_VIOLATION"
        ),
        diagnostic=(
            "Scenario stays inside the approved 1OZ/IBKR/$5k lower-frequency posture."
            if not posture_failures
            else (
                "Scenario violates the approved posture on constraints: "
                f"{[result.constraint for result in posture_failures]}"
            )
        ),
        evidence={
            "failed_constraints": [result.constraint for result in posture_failures],
            "posture_results": [result.to_dict() for result in posture_results],
        },
    )
    traces.append(posture_entry)
    for result in posture_failures:
        diffs.append(
            {
                "subject": result.constraint,
                "reason_code": result.reason_code,
                "expected": result.expected,
                "actual": result.actual,
                "diagnostic": result.diagnostic,
            }
        )

    profile_map = product_profiles_by_id()
    profile = profile_map.get(request.product_profile_id)
    if profile is None:
        profile_entry = _stage_entry(
            step_id="EL01",
            step_name="product_profile_binding",
            passed=False,
            reason_code="EXECUTION_LANE_PROFILE_UNKNOWN",
            diagnostic=f"Unknown product profile: {request.product_profile_id}",
            evidence={"product_profile_id": request.product_profile_id},
        )
        traces.append(profile_entry)
        diffs.append(
            {
                "subject": "product_profile_id",
                "reason_code": profile_entry.reason_code,
                "expected": "known profile id",
                "actual": request.product_profile_id,
                "diagnostic": profile_entry.diagnostic,
            }
        )
        return traces, diffs, {"profile": None}, False, False

    try:
        requested_lane = _coerce_lane(request.route_lane)
    except ValueError:
        lane_entry = _stage_entry(
            step_id="EL01",
            step_name="product_profile_binding",
            passed=False,
            reason_code="EXECUTION_LANE_LANE_UNKNOWN",
            diagnostic=f"Unknown route lane: {request.route_lane}",
            evidence={"route_lane": request.route_lane},
        )
        traces.append(lane_entry)
        diffs.append(
            {
                "subject": "route_lane",
                "reason_code": lane_entry.reason_code,
                "expected": [lane.value for lane in ProductLane],
                "actual": request.route_lane,
                "diagnostic": lane_entry.diagnostic,
            }
        )
        return traces, diffs, {"profile": profile}, False, False

    profile_supported = requested_lane in profile.supported_lanes
    symbol_matches = profile.contract_specification.symbol == request.execution_symbol
    broker_matches = profile.broker_capability_assumptions.broker == request.route_broker
    profile_passed = profile_supported and symbol_matches and broker_matches
    profile_entry = _stage_entry(
        step_id="EL01",
        step_name="product_profile_binding",
        passed=profile_passed,
        reason_code=(
            "EXECUTION_LANE_PROFILE_PASS"
            if profile_passed
            else "EXECUTION_LANE_PROFILE_MISMATCH"
        ),
        diagnostic=(
            f"Product profile {request.product_profile_id} supports lane {requested_lane.value} "
            f"for {request.execution_symbol} on {request.route_broker}."
            if profile_passed
            else (
                f"Product profile {request.product_profile_id} does not support the requested "
                "execution-lane binding."
            )
        ),
        evidence={
            "requested_lane": requested_lane.value,
            "supported_lanes": [lane.value for lane in profile.supported_lanes],
            "expected_execution_symbol": profile.contract_specification.symbol,
            "actual_execution_symbol": request.execution_symbol,
            "expected_broker": profile.broker_capability_assumptions.broker,
            "actual_broker": request.route_broker,
        },
    )
    traces.append(profile_entry)
    if not profile_passed:
        diffs.append(
            {
                "subject": "product_profile_binding",
                "reason_code": profile_entry.reason_code,
                "expected": {
                    "lane": [lane.value for lane in profile.supported_lanes],
                    "execution_symbol": profile.contract_specification.symbol,
                    "broker": profile.broker_capability_assumptions.broker,
                },
                "actual": {
                    "lane": requested_lane.value,
                    "execution_symbol": request.execution_symbol,
                    "broker": request.route_broker,
                },
                "diagnostic": profile_entry.diagnostic,
            }
        )

    common_valid = profile is not None and requested_lane is not None
    common_excluded = bool(posture_failures) or not profile_passed
    return traces, diffs, {"profile": profile, "requested_lane": requested_lane.value}, common_valid, common_excluded


def _artifact_entry(
    *,
    case_id: str,
    run_id: str,
    artifact_id: str,
    artifact_role: str,
    filename: str,
    payload: Any,
) -> ArtifactEntry:
    return ArtifactEntry(
        artifact_id=artifact_id,
        artifact_role=artifact_role,
        relative_path=f"reports/{run_id}/{case_id}/{filename}",
        sha256=_sha256_payload(payload),
        content_type="application/json",
    )


def _build_manifest(
    *,
    request: ExecutionLaneScenarioRequest,
    scenario_payload: dict[str, Any],
    report_payload: dict[str, Any],
) -> ArtifactManifest:
    artifacts = [
        _artifact_entry(
            case_id=request.case_id,
            run_id=request.run_id,
            artifact_id=f"{request.case_id}-request",
            artifact_role="scenario_request",
            filename="request.json",
            payload=request.to_dict(),
        ),
        _artifact_entry(
            case_id=request.case_id,
            run_id=request.run_id,
            artifact_id=f"{request.case_id}-scenario",
            artifact_role="scenario_report",
            filename=f"{request.scenario_kind}.json",
            payload=scenario_payload,
        ),
        _artifact_entry(
            case_id=request.case_id,
            run_id=request.run_id,
            artifact_id=f"{request.case_id}-final",
            artifact_role="decision_report",
            filename="report.json",
            payload=report_payload,
        ),
    ]
    return ArtifactManifest(
        manifest_id=f"manifest:{request.run_id}:{request.case_id}",
        generated_at_utc=_utcnow(),
        retention_class="verification_gate",
        contains_secrets=False,
        redaction_policy="credentials_redacted_by_construction",
        artifacts=[artifact.to_dict() for artifact in artifacts],
    )


def _structured_log_record(
    *,
    event_type: str,
    plane: str,
    request: ExecutionLaneScenarioRequest,
    reason_code: str,
    reason_summary: str,
    referenced_ids: dict[str, Any],
    manifest: ArtifactManifest,
) -> dict[str, Any]:
    return {
        "schema_version": SCENARIO_REPORT_SCHEMA_VERSION,
        "event_type": event_type,
        "plane": plane,
        "event_id": f"{request.case_id}:{event_type}",
        "recorded_at_utc": _utcnow(),
        "correlation_id": request.correlation_id,
        "decision_trace_id": request.decision_trace_id,
        "reason_code": reason_code,
        "reason_summary": reason_summary,
        "referenced_ids": referenced_ids,
        "redacted_fields": ["credentials", "account_identifiers"],
        "omitted_fields": [],
        "artifact_manifest": manifest.to_dict(),
    }


def _final_report(
    *,
    request: ExecutionLaneScenarioRequest,
    decision: ExecutionLaneScenarioDecision,
    reason_code: str,
    summary: str,
    decision_trace: list[ScenarioTraceEntry],
    expected_vs_actual_diffs: list[dict[str, Any]],
    vertical_slice_report: dict[str, Any] | None,
    calibration_report: dict[str, Any] | None,
) -> ExecutionLaneScenarioReport:
    partial_payload = {
        "case_id": request.case_id,
        "scenario_kind": request.scenario_kind,
        "decision": decision.value,
        "reason_code": reason_code,
        "decision_trace": [entry.to_dict() for entry in decision_trace],
        "vertical_slice_report": vertical_slice_report,
        "calibration_report": calibration_report,
    }
    manifest = _build_manifest(
        request=request,
        scenario_payload=vertical_slice_report or calibration_report or {},
        report_payload=partial_payload,
    )
    rule_trace = [
        {
            "step_id": entry.step_id,
            "reason_code": entry.reason_code,
            "passed": entry.passed,
        }
        for entry in decision_trace
    ]
    structured_logs = [
        _structured_log_record(
            event_type="execution_lane.context_evaluated",
            plane="policy",
            request=request,
            reason_code=decision_trace[0].reason_code,
            reason_summary=decision_trace[0].diagnostic,
            referenced_ids={
                "case_id": request.case_id,
                "candidate_id": request.candidate_id,
                "product_profile_id": request.product_profile_id,
            },
            manifest=manifest,
        ),
        _structured_log_record(
            event_type=f"execution_lane.{request.scenario_kind}.evaluated",
            plane=(
                "runtime"
                if request.scenario_kind == ExecutionLaneScenarioKind.VERTICAL_SLICE.value
                else "certification"
            ),
            request=request,
            reason_code=reason_code,
            reason_summary=summary,
            referenced_ids={
                "case_id": request.case_id,
                "candidate_id": request.candidate_id,
                "strategy_class_id": request.strategy_class_id,
                "run_id": request.run_id,
            },
            manifest=manifest,
        ),
        _structured_log_record(
            event_type="execution_lane.decision_recorded",
            plane="certification",
            request=request,
            reason_code=reason_code,
            reason_summary=summary,
            referenced_ids={
                "case_id": request.case_id,
                "decision": decision.value,
                "decision_trace_id": request.decision_trace_id,
            },
            manifest=manifest,
        ),
    ]
    operator_reason_bundle = {
        "summary": summary,
        "gate_summary": {
            "decision": decision.value,
            "scenario_kind": request.scenario_kind,
            "failed_steps": [entry.step_id for entry in decision_trace if not entry.passed],
        },
        "rule_trace": rule_trace,
        "remediation_hints": (
            []
            if decision == ExecutionLaneScenarioDecision.PASS
            else [
                "Inspect the failing decision-trace steps and expected-vs-actual diffs.",
                "Re-run the smoke script for the specific case after correcting the failed lane checks.",
            ]
        ),
    }
    return ExecutionLaneScenarioReport(
        schema_version=SCENARIO_REPORT_SCHEMA_VERSION,
        case_id=request.case_id,
        scenario_kind=request.scenario_kind,
        decision=decision.value,
        reason_code=reason_code,
        correlation_id=request.correlation_id,
        decision_trace_id=request.decision_trace_id,
        run_id=request.run_id,
        candidate_id=request.candidate_id,
        strategy_class_id=request.strategy_class_id,
        product_profile_id=request.product_profile_id,
        preserved_input_artifact_ids=request.preserved_input_artifact_ids,
        supporting_data_refs=request.supporting_data_refs,
        expected_vs_actual_diffs=expected_vs_actual_diffs,
        operator_reason_bundle=operator_reason_bundle,
        artifact_manifest=manifest.to_dict(),
        structured_logs=structured_logs,
        decision_trace=[entry.to_dict() for entry in decision_trace],
        vertical_slice_report=vertical_slice_report,
        calibration_report=calibration_report,
    )


def _evaluate_vertical_slice(
    request: ExecutionLaneScenarioRequest,
    common_trace: list[ScenarioTraceEntry],
    expected_vs_actual_diffs: list[dict[str, Any]],
    common_valid: bool,
    common_excluded: bool,
) -> ExecutionLaneScenarioReport:
    if request.vertical_slice is None:
        return _final_report(
            request=request,
            decision=ExecutionLaneScenarioDecision.INVALID,
            reason_code="EXECUTION_LANE_VERTICAL_SLICE_INPUTS_REQUIRED",
            summary="Vertical-slice scenario requests must include vertical_slice inputs.",
            decision_trace=common_trace,
            expected_vs_actual_diffs=expected_vs_actual_diffs,
            vertical_slice_report=None,
            calibration_report=None,
        )

    traces = list(common_trace)
    sentinel_passed = (
        request.vertical_slice.sentinel_strategy_route
        == request.vertical_slice.expected_sentinel_strategy_route
    )
    traces.append(
        _stage_entry(
            step_id="EL10",
            step_name="sentinel_strategy_route",
            passed=sentinel_passed,
            reason_code=(
                "EXECUTION_LANE_SENTINEL_ROUTE_PASS"
                if sentinel_passed
                else "EXECUTION_LANE_SENTINEL_ROUTE_MISMATCH"
            ),
            diagnostic=(
                "Sentinel strategy route matches the non-economic IBKR paper route."
                if sentinel_passed
                else (
                    "Sentinel strategy route does not match the expected paper-route "
                    f"binding: {request.vertical_slice.sentinel_strategy_route} vs "
                    f"{request.vertical_slice.expected_sentinel_strategy_route}."
                )
            ),
            evidence={
                "expected": request.vertical_slice.expected_sentinel_strategy_route,
                "actual": request.vertical_slice.sentinel_strategy_route,
            },
        )
    )
    if not sentinel_passed:
        expected_vs_actual_diffs.append(
            {
                "subject": "sentinel_strategy_route",
                "reason_code": "EXECUTION_LANE_SENTINEL_ROUTE_MISMATCH",
                "expected": request.vertical_slice.expected_sentinel_strategy_route,
                "actual": request.vertical_slice.sentinel_strategy_route,
                "diagnostic": "Sentinel route mismatch blocks the vertical slice.",
            }
        )

    reconnect_passed = request.vertical_slice.broker_reconnect_observed
    traces.append(
        _stage_entry(
            step_id="EL11",
            step_name="broker_reconnect_observation",
            passed=reconnect_passed,
            reason_code=(
                "EXECUTION_LANE_RECONNECT_OBSERVED"
                if reconnect_passed
                else "EXECUTION_LANE_RECONNECT_NOT_OBSERVED"
            ),
            diagnostic=(
                "Broker reconnect observation was retained for the vertical slice."
                if reconnect_passed
                else "Broker reconnect observation is missing from the vertical slice evidence."
            ),
            evidence={
                "reconnect_observed": request.vertical_slice.broker_reconnect_observed,
                "reference": request.vertical_slice.reconnect_observation_reference,
            },
        )
    )
    if not reconnect_passed:
        expected_vs_actual_diffs.append(
            {
                "subject": "broker_reconnect_observation",
                "reason_code": "EXECUTION_LANE_RECONNECT_NOT_OBSERVED",
                "expected": True,
                "actual": False,
                "diagnostic": "A broker reconnect observation is required for the vertical slice.",
            }
        )

    viability_report = evaluate_viability_gate(**request.vertical_slice.viability_gate_inputs)
    traces.append(
        _stage_entry(
            step_id="EL12",
            step_name="vertical_slice_viability_gate",
            passed=viability_report.gate_passed,
            reason_code=viability_report.reason_code,
            diagnostic=viability_report.rationale,
            evidence={
                "outcome": viability_report.outcome,
                "failed_checks": [
                    check["check_id"] for check in viability_report.checks if not check["passed"]
                ],
            },
        )
    )
    for check in viability_report.checks:
        if not check["passed"]:
            expected_vs_actual_diffs.append(
                {
                    "subject": check["check_name"],
                    "reason_code": check["reason_code"],
                    "expected": "lane check pass",
                    "actual": check["evidence"],
                    "diagnostic": check["diagnostic"],
                }
            )

    if not common_valid:
        decision = ExecutionLaneScenarioDecision.INVALID
        reason_code = "EXECUTION_LANE_VERTICAL_SLICE_INVALID"
        summary = "The vertical-slice scenario request is malformed or references unknown lane metadata."
    elif common_excluded or viability_report.outcome == GateOutcome.TERMINATE.value:
        decision = ExecutionLaneScenarioDecision.EXCLUDED
        reason_code = "EXECUTION_LANE_VERTICAL_SLICE_EXCLUDED"
        summary = (
            "The vertical slice is outside the approved execution lane or failed with a "
            "terminate-grade viability outcome."
        )
    elif viability_report.gate_passed and sentinel_passed and reconnect_passed:
        decision = ExecutionLaneScenarioDecision.PASS
        reason_code = "EXECUTION_LANE_VERTICAL_SLICE_PASS"
        summary = (
            "The non-economic IBKR/1OZ vertical slice passed posture, routing, reconnect, "
            "and five-lane viability checks."
        )
    else:
        decision = ExecutionLaneScenarioDecision.PIVOT
        reason_code = "EXECUTION_LANE_VERTICAL_SLICE_PIVOT"
        summary = (
            "The vertical slice retained enough evidence to diagnose a pivot or narrow follow-up, "
            "but it is not admissible as a clean pass."
        )

    traces.append(
        _stage_entry(
            step_id="EL19",
            step_name="vertical_slice_final_decision",
            passed=decision == ExecutionLaneScenarioDecision.PASS,
            reason_code=reason_code,
            diagnostic=summary,
            evidence={"decision": decision.value},
        )
    )
    return _final_report(
        request=request,
        decision=decision,
        reason_code=reason_code,
        summary=summary,
        decision_trace=traces,
        expected_vs_actual_diffs=expected_vs_actual_diffs,
        vertical_slice_report={
            "sentinel_strategy_route": request.vertical_slice.sentinel_strategy_route,
            "expected_sentinel_strategy_route": request.vertical_slice.expected_sentinel_strategy_route,
            "broker_reconnect_observed": request.vertical_slice.broker_reconnect_observed,
            "reconnect_observation_reference": request.vertical_slice.reconnect_observation_reference,
            "viability_gate": viability_report.to_dict(),
        },
        calibration_report=None,
    )


def _evaluate_calibration(
    request: ExecutionLaneScenarioRequest,
    common_trace: list[ScenarioTraceEntry],
    expected_vs_actual_diffs: list[dict[str, Any]],
    common_valid: bool,
    common_excluded: bool,
) -> ExecutionLaneScenarioReport:
    if request.calibration is None:
        return _final_report(
            request=request,
            decision=ExecutionLaneScenarioDecision.INVALID,
            reason_code="EXECUTION_LANE_CALIBRATION_INPUTS_REQUIRED",
            summary="Calibration scenario requests must include calibration inputs.",
            decision_trace=common_trace,
            expected_vs_actual_diffs=expected_vs_actual_diffs,
            vertical_slice_report=None,
            calibration_report=None,
        )

    traces = list(common_trace)
    viability_report = evaluate_execution_symbol_first_viability_screen(
        research_symbol=request.research_symbol,
        execution_symbol=request.execution_symbol,
        candidate_id=request.candidate_id,
        research_artifact_id=request.calibration.research_artifact_id,
        native_execution_history_obtained=request.calibration.native_execution_history_obtained,
        live_or_paper_observations_obtained=request.calibration.live_or_paper_observations_obtained,
        dimensions=list(request.calibration.execution_symbol_dimensions),
    )
    traces.append(
        _stage_entry(
            step_id="EL20",
            step_name="execution_symbol_first_viability",
            passed=viability_report.deep_promotable_budget_allowed,
            reason_code=viability_report.reason_code,
            diagnostic=viability_report.rationale,
            evidence={
                "outcome_recommendation": viability_report.outcome_recommendation,
                "failed_dimensions": [
                    item["dimension_id"] for item in viability_report.dimensions if not item["passed"]
                ],
            },
        )
    )
    for dimension in viability_report.dimensions:
        if not dimension["passed"]:
            expected_vs_actual_diffs.append(
                {
                    "subject": dimension["dimension_name"],
                    "reason_code": dimension["reason_code"],
                    "expected": dimension["threshold"],
                    "actual": dimension["measured_value"],
                    "diagnostic": dimension["diagnostic"],
                }
            )

    certification_report = evaluate_portability_and_native_validation(
        research_symbol=request.research_symbol,
        execution_symbol=request.execution_symbol,
        finalist_id=request.candidate_id,
        execution_symbol_viability_report_id=f"{request.case_id}:execution_symbol_viability",
        execution_symbol_viability_passed=viability_report.viability_passed,
        portability_study_id=request.calibration.portability_study_id,
        portability_dimensions=list(request.calibration.portability_dimensions),
        sufficient_native_1oz_history_exists=request.calibration.sufficient_native_1oz_history_exists,
        native_1oz_validation_study_id=request.calibration.native_1oz_validation_study_id,
        native_1oz_validation_passed=request.calibration.native_1oz_validation_passed,
    )
    traces.append(
        _stage_entry(
            step_id="EL21",
            step_name="portability_and_native_validation",
            passed=certification_report.promotable_finalist_allowed,
            reason_code=certification_report.reason_code,
            diagnostic=certification_report.rationale,
            evidence={
                "outcome_recommendation": certification_report.outcome_recommendation,
                "portability_certified": certification_report.portability_certified,
                "native_1oz_validation_required": certification_report.native_1oz_validation_required,
                "native_1oz_validation_passed": certification_report.native_1oz_validation_passed,
            },
        )
    )
    for dimension in certification_report.portability_dimensions:
        if not dimension["passed"]:
            expected_vs_actual_diffs.append(
                {
                    "subject": dimension["dimension_name"],
                    "reason_code": dimension["reason_code"],
                    "expected": dimension["threshold"],
                    "actual": dimension["measured_value"],
                    "diagnostic": dimension["diagnostic"],
                }
            )

    fidelity_report = evaluate_fidelity_calibration(
        strategy_class_id=request.strategy_class_id,
        calibration_evidence_report_id=request.calibration.calibration_evidence_report_id,
        dimensions=list(request.calibration.fidelity_dimensions),
        decision_interval_seconds=request.calibration.decision_interval_seconds,
        uses_bar_based_logic=request.calibration.uses_bar_based_logic,
        uses_one_bar_late_decisions=request.calibration.uses_one_bar_late_decisions,
        depends_on_order_book_imbalance=request.calibration.depends_on_order_book_imbalance,
        requires_queue_position_edge=request.calibration.requires_queue_position_edge,
        requires_sub_minute_market_making=request.calibration.requires_sub_minute_market_making,
        requires_premium_live_depth_data=request.calibration.requires_premium_live_depth_data,
    )
    traces.append(
        _stage_entry(
            step_id="EL22",
            step_name="fidelity_calibration_and_live_lane",
            passed=fidelity_report.promotable_for_live_lane,
            reason_code=fidelity_report.reason_code,
            diagnostic=fidelity_report.rationale,
            evidence={
                "live_lane_eligible": fidelity_report.live_lane_eligible,
                "failed_dimensions": [
                    item["dimension_id"] for item in fidelity_report.dimensions if not item["passed"]
                ],
                "excluded_reason_codes": fidelity_report.lower_frequency_live_lane["exclusion_reason_codes"],
            },
        )
    )
    for dimension in fidelity_report.dimensions:
        if not dimension["passed"]:
            expected_vs_actual_diffs.append(
                {
                    "subject": dimension["dimension_name"],
                    "reason_code": dimension["reason_code"],
                    "expected": dimension["threshold"],
                    "actual": dimension["measured_value"],
                    "diagnostic": dimension["diagnostic"],
                }
            )
    for check in fidelity_report.lower_frequency_live_lane["checks"]:
        if not check["passed"]:
            expected_vs_actual_diffs.append(
                {
                    "subject": check["constraint_name"],
                    "reason_code": check["reason_code"],
                    "expected": check["threshold"],
                    "actual": check["measured_value"],
                    "diagnostic": check["diagnostic"],
                }
            )

    if not common_valid:
        decision = ExecutionLaneScenarioDecision.INVALID
        reason_code = "EXECUTION_LANE_CALIBRATION_INVALID"
        summary = "The calibration scenario request is malformed or references unknown lane metadata."
    elif common_excluded:
        decision = ExecutionLaneScenarioDecision.EXCLUDED
        reason_code = "EXECUTION_LANE_CALIBRATION_EXCLUDED"
        summary = "The calibration scenario falls outside the approved execution-lane posture or profile."
    elif not fidelity_report.live_lane_eligible:
        decision = ExecutionLaneScenarioDecision.EXCLUDED
        reason_code = "EXECUTION_LANE_CALIBRATION_EXCLUDED"
        summary = (
            "The strategy is explicitly excluded from the approved lower-frequency live lane."
        )
    elif (
        certification_report.outcome_recommendation == GateOutcome.TERMINATE.value
        or viability_report.outcome_recommendation == GateOutcome.TERMINATE.value
    ):
        decision = ExecutionLaneScenarioDecision.EXCLUDED
        reason_code = "EXECUTION_LANE_CALIBRATION_EXCLUDED"
        summary = (
            "Execution-symbol viability or native validation produced an exclusion-grade outcome."
        )
    elif (
        certification_report.promotable_finalist_allowed
        and fidelity_report.promotable_for_live_lane
    ):
        decision = ExecutionLaneScenarioDecision.PASS
        reason_code = "EXECUTION_LANE_CALIBRATION_PASS"
        summary = (
            "Execution-symbol viability, portability certification, and lower-frequency fidelity "
            "calibration all passed."
        )
    else:
        decision = ExecutionLaneScenarioDecision.PIVOT
        reason_code = "EXECUTION_LANE_CALIBRATION_PIVOT"
        summary = (
            "Calibration evidence is retained and explainable, but more portability, native 1OZ, "
            "or lower-frequency evidence is still required."
        )

    traces.append(
        _stage_entry(
            step_id="EL29",
            step_name="calibration_final_decision",
            passed=decision == ExecutionLaneScenarioDecision.PASS,
            reason_code=reason_code,
            diagnostic=summary,
            evidence={"decision": decision.value},
        )
    )
    calibration_report = {
        "execution_symbol_viability": viability_report.to_dict(),
        "portability_and_native_validation": certification_report.to_dict(),
        "fidelity_calibration": fidelity_report.to_dict(),
    }
    return _final_report(
        request=request,
        decision=decision,
        reason_code=reason_code,
        summary=summary,
        decision_trace=traces,
        expected_vs_actual_diffs=expected_vs_actual_diffs,
        vertical_slice_report=None,
        calibration_report=calibration_report,
    )


def evaluate_execution_lane_scenario(
    request: ExecutionLaneScenarioRequest,
) -> ExecutionLaneScenarioReport:
    """Evaluate one execution-lane scenario request."""

    kind = ExecutionLaneScenarioKind(request.scenario_kind)
    common_trace, diffs, _, common_valid, common_excluded = _common_context(request)
    if kind == ExecutionLaneScenarioKind.VERTICAL_SLICE:
        return _evaluate_vertical_slice(
            request,
            common_trace=common_trace,
            expected_vs_actual_diffs=diffs,
            common_valid=common_valid,
            common_excluded=common_excluded,
        )
    return _evaluate_calibration(
        request,
        common_trace=common_trace,
        expected_vs_actual_diffs=diffs,
        common_valid=common_valid,
        common_excluded=common_excluded,
    )
