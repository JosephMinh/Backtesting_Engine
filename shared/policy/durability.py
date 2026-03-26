"""Durability, backup, restore, and restore-drill policy contracts."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DurabilityControl:
    key: str
    title: str
    plan_section: str
    expected_control: str
    resolution_guidance: str


@dataclass(frozen=True)
class RecoveryObjective:
    key: str
    title: str
    plan_section: str
    rpo_max_minutes: int | None
    rto_max_minutes: int | None
    protected_assets: tuple[str, ...]
    resolution_guidance: str


@dataclass(frozen=True)
class DurabilityDiagnostic:
    control: str
    status: str
    reason_code: str | None
    plan_section: str
    evidence_surface: str
    expected_control: str
    diagnostic_context: dict[str, object]
    resolution_guidance: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


DURABILITY_CONTROLS: tuple[DurabilityControl, ...] = (
    DurabilityControl(
        key="postgres_pitr_backup",
        title="PostgreSQL backup plus point-in-time recovery coverage",
        plan_section="3.6",
        expected_control=(
            "Canonical metadata and operational state use automated database "
            "backups plus WAL archiving or equivalent point-in-time recovery coverage."
        ),
        resolution_guidance=(
            "Enable WAL archiving or an equivalent PITR path and keep recovery-point "
            "lag inside the approved RPO."
        ),
    ),
    DurabilityControl(
        key="off_host_durability",
        title="Off-host durability and failure-domain separation",
        plan_section="3.6",
        expected_control=(
            "Backups, evidence, journals, and snapshots are retained in off-host "
            "versioned or append-only storage that does not share the live failure domain."
        ),
        resolution_guidance=(
            "Move durability artifacts to versioned or append-only off-host storage "
            "outside the live host or VM failure domain."
        ),
    ),
    DurabilityControl(
        key="tamper_evident_journals",
        title="Tamper-evident journals and snapshot barriers",
        plan_section="3.6",
        expected_control=(
            "Economically significant journals and snapshot barriers use tamper-evident hash chaining."
        ),
        resolution_guidance=(
            "Hash-chain journals and snapshot barriers before approving the live-capable baseline."
        ),
    ),
    DurabilityControl(
        key="restore_evidence",
        title="Restore manifests and runbooks",
        plan_section="3.6",
        expected_control=(
            "Restore manifests bind database backups to object-store checkpoints and documented runbooks."
        ),
        resolution_guidance=(
            "Publish restore manifests that bind the database backup to the artifact-store checkpoint and keep the runbook current."
        ),
    ),
    DurabilityControl(
        key="restore_drill",
        title="Restore-drill evidence and safety",
        plan_section="3.6",
        expected_control=(
            "Restore drills run before first live approval and at least quarterly thereafter, with integrity verification, structured logs, and safe repeatability."
        ),
        resolution_guidance=(
            "Run full restore drills on a test environment, capture structured evidence, and measure recovery outcomes against the approved targets."
        ),
    ),
)


RECOVERY_OBJECTIVES: tuple[RecoveryObjective, ...] = (
    RecoveryObjective(
        key="canonical_metadata_and_live_state",
        title="Canonical metadata and live state",
        plan_section="3.6",
        rpo_max_minutes=15,
        rto_max_minutes=None,
        protected_assets=("canonical_metadata", "operational_state"),
        resolution_guidance=(
            "Keep recovery-point lag for canonical metadata and operational state at or below 15 minutes."
        ),
    ),
    RecoveryObjective(
        key="live_capable_host",
        title="Live-capable host recovery",
        plan_section="3.6",
        rpo_max_minutes=None,
        rto_max_minutes=240,
        protected_assets=("live_host", "runtime_services"),
        resolution_guidance=(
            "Restore the live-capable host or replacement VM within four hours."
        ),
    ),
    RecoveryObjective(
        key="raw_historical_reingestion",
        title="Raw historical re-ingestion",
        plan_section="3.6",
        rpo_max_minutes=None,
        rto_max_minutes=None,
        protected_assets=("raw_archives",),
        resolution_guidance=(
            "Document deterministic vendor re-pull before relying on looser raw-history recovery targets."
        ),
    ),
)


_CONTROL_INDEX: dict[str, DurabilityControl] = {
    control.key: control for control in DURABILITY_CONTROLS
}
_OBJECTIVE_INDEX: dict[str, RecoveryObjective] = {
    objective.key: objective for objective in RECOVERY_OBJECTIVES
}


def durability_control_keys() -> list[str]:
    return [control.key for control in DURABILITY_CONTROLS]


def recovery_objective_keys() -> list[str]:
    return [objective.key for objective in RECOVERY_OBJECTIVES]


def _diagnostic(
    *,
    control: str,
    status: str,
    reason_code: str | None,
    plan_section: str,
    evidence_surface: str,
    expected_control: str,
    diagnostic_context: dict[str, object],
    resolution_guidance: str,
    explanation: str,
) -> DurabilityDiagnostic:
    return DurabilityDiagnostic(
        control=control,
        status=status,
        reason_code=reason_code,
        plan_section=plan_section,
        evidence_surface=evidence_surface,
        expected_control=expected_control,
        diagnostic_context=diagnostic_context,
        resolution_guidance=resolution_guidance,
        explanation=explanation,
    )


def evaluate_backup_coverage(
    *,
    recovery_point_lag_minutes: int,
    wal_archiving_enabled: bool,
    equivalent_point_in_time_coverage: bool,
    backup_freshness_green: bool,
) -> DurabilityDiagnostic:
    control = _CONTROL_INDEX["postgres_pitr_backup"]
    context = {
        "recovery_point_lag_minutes": recovery_point_lag_minutes,
        "wal_archiving_enabled": wal_archiving_enabled,
        "equivalent_point_in_time_coverage": equivalent_point_in_time_coverage,
        "backup_freshness_green": backup_freshness_green,
    }
    coverage_ready = wal_archiving_enabled or equivalent_point_in_time_coverage
    rpo_ready = recovery_point_lag_minutes <= 15

    if coverage_ready and rpo_ready and backup_freshness_green:
        return _diagnostic(
            control=control.key,
            status="pass",
            reason_code=None,
            plan_section=control.plan_section,
            evidence_surface="database_backup",
            expected_control=control.expected_control,
            diagnostic_context=context,
            resolution_guidance=control.resolution_guidance,
            explanation="Database backup coverage supports point-in-time recovery inside the approved RPO.",
        )

    if not coverage_ready:
        reason_code = "DURABILITY_BACKUP_PITR_NOT_AVAILABLE"
        explanation = "Database backup coverage lacks WAL archiving or an equivalent point-in-time recovery path."
    elif not backup_freshness_green:
        reason_code = "DURABILITY_BACKUP_FRESHNESS_STALE"
        explanation = "Backup freshness is not green, so live approval inputs would be stale."
    else:
        reason_code = "DURABILITY_RPO_EXCEEDED"
        explanation = "Recovery-point lag exceeds the approved 15-minute ceiling."

    return _diagnostic(
        control=control.key,
        status="violation",
        reason_code=reason_code,
        plan_section=control.plan_section,
        evidence_surface="database_backup",
        expected_control=control.expected_control,
        diagnostic_context=context,
        resolution_guidance=control.resolution_guidance,
        explanation=explanation,
    )


def evaluate_off_host_durability(
    *,
    off_host_storage_present: bool,
    storage_mode: str,
    same_failure_domain: bool,
) -> DurabilityDiagnostic:
    control = _CONTROL_INDEX["off_host_durability"]
    context = {
        "off_host_storage_present": off_host_storage_present,
        "storage_mode": storage_mode,
        "same_failure_domain": same_failure_domain,
    }
    storage_mode_ok = storage_mode in {"versioned", "append_only"}

    if off_host_storage_present and storage_mode_ok and not same_failure_domain:
        return _diagnostic(
            control=control.key,
            status="pass",
            reason_code=None,
            plan_section=control.plan_section,
            evidence_surface="object_storage",
            expected_control=control.expected_control,
            diagnostic_context=context,
            resolution_guidance=control.resolution_guidance,
            explanation="Durability artifacts are retained off-host with the required isolation and retention mode.",
        )

    if not off_host_storage_present:
        reason_code = "DURABILITY_OFF_HOST_STORAGE_MISSING"
        explanation = "Off-host storage is missing for backups, evidence, journals, or snapshots."
    elif same_failure_domain:
        reason_code = "DURABILITY_FAILURE_DOMAIN_SHARED"
        explanation = "Durability targets still share the same failure domain as the live host or VM."
    else:
        reason_code = "DURABILITY_STORAGE_MODE_NOT_IMMUTABLE"
        explanation = "Durability storage is not versioned or append-only."

    return _diagnostic(
        control=control.key,
        status="violation",
        reason_code=reason_code,
        plan_section=control.plan_section,
        evidence_surface="object_storage",
        expected_control=control.expected_control,
        diagnostic_context=context,
        resolution_guidance=control.resolution_guidance,
        explanation=explanation,
    )


def evaluate_tamper_evidence(
    *,
    journals_hash_chained: bool,
    snapshot_barriers_hash_chained: bool,
) -> DurabilityDiagnostic:
    control = _CONTROL_INDEX["tamper_evident_journals"]
    context = {
        "journals_hash_chained": journals_hash_chained,
        "snapshot_barriers_hash_chained": snapshot_barriers_hash_chained,
    }

    if journals_hash_chained and snapshot_barriers_hash_chained:
        return _diagnostic(
            control=control.key,
            status="pass",
            reason_code=None,
            plan_section=control.plan_section,
            evidence_surface="journal_chain",
            expected_control=control.expected_control,
            diagnostic_context=context,
            resolution_guidance=control.resolution_guidance,
            explanation="Journals and snapshot barriers are tamper-evident.",
        )

    return _diagnostic(
        control=control.key,
        status="violation",
        reason_code="DURABILITY_HASH_CHAIN_INCOMPLETE",
        plan_section=control.plan_section,
        evidence_surface="journal_chain",
        expected_control=control.expected_control,
        diagnostic_context=context,
        resolution_guidance=control.resolution_guidance,
        explanation="Journals or snapshot barriers are not fully protected by tamper-evident hash chaining.",
    )


def evaluate_restore_artifacts(
    *,
    restore_manifest_present: bool,
    manifest_binds_database_backup: bool,
    manifest_binds_artifact_checkpoint: bool,
    restore_runbook_present: bool,
) -> DurabilityDiagnostic:
    control = _CONTROL_INDEX["restore_evidence"]
    context = {
        "restore_manifest_present": restore_manifest_present,
        "manifest_binds_database_backup": manifest_binds_database_backup,
        "manifest_binds_artifact_checkpoint": manifest_binds_artifact_checkpoint,
        "restore_runbook_present": restore_runbook_present,
    }

    if (
        restore_manifest_present
        and manifest_binds_database_backup
        and manifest_binds_artifact_checkpoint
        and restore_runbook_present
    ):
        return _diagnostic(
            control=control.key,
            status="pass",
            reason_code=None,
            plan_section=control.plan_section,
            evidence_surface="restore_manifest",
            expected_control=control.expected_control,
            diagnostic_context=context,
            resolution_guidance=control.resolution_guidance,
            explanation="Restore manifests and runbooks are present and bind the required recovery checkpoints.",
        )

    if not restore_manifest_present:
        reason_code = "DURABILITY_RESTORE_MANIFEST_MISSING"
        explanation = "Restore manifest evidence is missing."
    elif not manifest_binds_database_backup or not manifest_binds_artifact_checkpoint:
        reason_code = "DURABILITY_RESTORE_MANIFEST_INCOMPLETE"
        explanation = "Restore manifest does not bind both the database backup and the artifact-store checkpoint."
    else:
        reason_code = "DURABILITY_RESTORE_RUNBOOK_MISSING"
        explanation = "Restore runbook evidence is missing."

    return _diagnostic(
        control=control.key,
        status="violation",
        reason_code=reason_code,
        plan_section=control.plan_section,
        evidence_surface="restore_manifest",
        expected_control=control.expected_control,
        diagnostic_context=context,
        resolution_guidance=control.resolution_guidance,
        explanation=explanation,
    )


def evaluate_recovery_objective(
    objective_key: str,
    *,
    measured_data_loss_window_minutes: int,
    measured_rto_minutes: int,
    deterministic_vendor_repull_documented: bool,
) -> DurabilityDiagnostic:
    objective = _OBJECTIVE_INDEX[objective_key]
    context = {
        "measured_data_loss_window_minutes": measured_data_loss_window_minutes,
        "measured_rto_minutes": measured_rto_minutes,
        "deterministic_vendor_repull_documented": deterministic_vendor_repull_documented,
    }
    expected_control = objective.resolution_guidance

    if objective.key == "canonical_metadata_and_live_state":
        passed = measured_data_loss_window_minutes <= 15
        reason_code = None if passed else "DURABILITY_RPO_TARGET_MISSED"
        explanation = (
            "Measured data-loss window stays inside the approved 15-minute RPO."
            if passed
            else "Measured data-loss window exceeds the approved 15-minute RPO."
        )
    elif objective.key == "live_capable_host":
        passed = measured_rto_minutes <= 240
        reason_code = None if passed else "DURABILITY_RTO_TARGET_MISSED"
        explanation = (
            "Measured host recovery time stays inside the approved four-hour RTO."
            if passed
            else "Measured host recovery time exceeds the approved four-hour RTO."
        )
    else:
        passed = deterministic_vendor_repull_documented
        reason_code = (
            None if passed else "DURABILITY_RAW_REINGESTION_UNDOCUMENTED"
        )
        explanation = (
            "Raw-history recovery relies on a documented deterministic vendor re-pull."
            if passed
            else "Raw-history recovery has no documented deterministic vendor re-pull."
        )

    return _diagnostic(
        control=objective.key,
        status="pass" if passed else "violation",
        reason_code=reason_code,
        plan_section=objective.plan_section,
        evidence_surface="recovery_objective",
        expected_control=expected_control,
        diagnostic_context=context,
        resolution_guidance=objective.resolution_guidance,
        explanation=explanation,
    )


def evaluate_restore_drill(
    *,
    before_first_live_approval: bool,
    last_drill_age_days: int,
    last_drill_succeeded: bool,
    files_restored: int,
    expected_files: int,
    hashes_match: bool,
    recovery_point_verified: bool,
    structured_logs_present: bool,
    timing_metrics_present: bool,
    data_loss_window_measured: bool,
    rpo_metric_present: bool,
    rto_metric_present: bool,
    correlation_id_present: bool,
    expected_vs_actual_diff_present: bool,
    artifact_manifest_present: bool,
    operator_reason_bundle_present: bool,
    idempotent: bool,
    safe_for_test_environments: bool,
) -> list[DurabilityDiagnostic]:
    control = _CONTROL_INDEX["restore_drill"]
    diagnostics: list[DurabilityDiagnostic] = []

    recency_context = {
        "before_first_live_approval": before_first_live_approval,
        "last_drill_age_days": last_drill_age_days,
        "last_drill_succeeded": last_drill_succeeded,
    }
    recency_ok = last_drill_succeeded and last_drill_age_days >= 0
    if before_first_live_approval:
        recency_ok = recency_ok and last_drill_age_days == 0
    else:
        recency_ok = recency_ok and last_drill_age_days <= 90
    diagnostics.append(
        _diagnostic(
            control=control.key,
            status="pass" if recency_ok else "violation",
            reason_code=None if recency_ok else "DURABILITY_RESTORE_DRILL_STALE",
            plan_section=control.plan_section,
            evidence_surface="restore_drill_schedule",
            expected_control=control.expected_control,
            diagnostic_context=recency_context,
            resolution_guidance=control.resolution_guidance,
            explanation=(
                "Restore-drill recency and success satisfy the approval cadence."
                if recency_ok
                else "Restore drill is missing, stale, or unsuccessful for the required approval cadence."
            ),
        )
    )

    integrity_context = {
        "files_restored": files_restored,
        "expected_files": expected_files,
        "hashes_match": hashes_match,
        "recovery_point_verified": recovery_point_verified,
    }
    integrity_ok = (
        files_restored == expected_files and hashes_match and recovery_point_verified
    )
    diagnostics.append(
        _diagnostic(
            control=control.key,
            status="pass" if integrity_ok else "violation",
            reason_code=None if integrity_ok else "DURABILITY_RESTORE_INTEGRITY_FAILED",
            plan_section=control.plan_section,
            evidence_surface="restore_drill_integrity",
            expected_control=(
                "Restore drills verify full data integrity with file-count, hash, and recovery-point checks."
            ),
            diagnostic_context=integrity_context,
            resolution_guidance=control.resolution_guidance,
            explanation=(
                "Restore drill verified file-count, hash, and recovery-point integrity."
                if integrity_ok
                else "Restore drill failed file-count, hash, or recovery-point verification."
            ),
        )
    )

    observability_context = {
        "structured_logs_present": structured_logs_present,
        "timing_metrics_present": timing_metrics_present,
        "data_loss_window_measured": data_loss_window_measured,
        "rpo_metric_present": rpo_metric_present,
        "rto_metric_present": rto_metric_present,
        "correlation_id_present": correlation_id_present,
        "expected_vs_actual_diff_present": expected_vs_actual_diff_present,
        "artifact_manifest_present": artifact_manifest_present,
        "operator_reason_bundle_present": operator_reason_bundle_present,
    }
    observability_ok = all(observability_context.values())
    diagnostics.append(
        _diagnostic(
            control=control.key,
            status="pass" if observability_ok else "violation",
            reason_code=None if observability_ok else "DURABILITY_RESTORE_OBSERVABILITY_INCOMPLETE",
            plan_section=control.plan_section,
            evidence_surface="restore_drill_observability",
            expected_control=(
                "Restore drills emit structured logs, timing metrics, loss-window measures, diffs, manifests, correlation IDs, and operator-readable reason bundles."
            ),
            diagnostic_context=observability_context,
            resolution_guidance=control.resolution_guidance,
            explanation=(
                "Restore drill emitted the full required observability bundle."
                if observability_ok
                else "Restore drill evidence is missing required logs, metrics, or retained artifacts."
            ),
        )
    )

    safety_context = {
        "idempotent": idempotent,
        "safe_for_test_environments": safe_for_test_environments,
    }
    safety_ok = idempotent and safe_for_test_environments
    diagnostics.append(
        _diagnostic(
            control=control.key,
            status="pass" if safety_ok else "violation",
            reason_code=None if safety_ok else "DURABILITY_RESTORE_DRILL_NOT_SAFE",
            plan_section=control.plan_section,
            evidence_surface="restore_drill_safety",
            expected_control=(
                "Restore drills are idempotent and safe to repeat in non-production test environments."
            ),
            diagnostic_context=safety_context,
            resolution_guidance=control.resolution_guidance,
            explanation=(
                "Restore drill workflow is idempotent and safe for repeated test execution."
                if safety_ok
                else "Restore drill workflow is not safe for repeated test execution."
            ),
        )
    )

    return diagnostics


def evaluate_durability_policy(
    *,
    backup_posture: dict[str, object],
    restore_evidence: dict[str, object],
    restore_drill: dict[str, object],
    recovery_metrics: dict[str, object],
) -> dict[str, object]:
    diagnostics = [
        evaluate_backup_coverage(
            recovery_point_lag_minutes=int(
                backup_posture["recovery_point_lag_minutes"]
            ),
            wal_archiving_enabled=bool(backup_posture["wal_archiving_enabled"]),
            equivalent_point_in_time_coverage=bool(
                backup_posture.get("equivalent_point_in_time_coverage", False)
            ),
            backup_freshness_green=bool(backup_posture["backup_freshness_green"]),
        ),
        evaluate_off_host_durability(
            off_host_storage_present=bool(backup_posture["off_host_storage_present"]),
            storage_mode=str(backup_posture["storage_mode"]),
            same_failure_domain=bool(backup_posture["same_failure_domain"]),
        ),
        evaluate_tamper_evidence(
            journals_hash_chained=bool(backup_posture["journals_hash_chained"]),
            snapshot_barriers_hash_chained=bool(
                backup_posture["snapshot_barriers_hash_chained"]
            ),
        ),
        evaluate_restore_artifacts(
            restore_manifest_present=bool(restore_evidence["restore_manifest_present"]),
            manifest_binds_database_backup=bool(
                restore_evidence["manifest_binds_database_backup"]
            ),
            manifest_binds_artifact_checkpoint=bool(
                restore_evidence["manifest_binds_artifact_checkpoint"]
            ),
            restore_runbook_present=bool(restore_evidence["restore_runbook_present"]),
        ),
    ]

    diagnostics.extend(
        evaluate_restore_drill(
            before_first_live_approval=bool(
                restore_drill["before_first_live_approval"]
            ),
            last_drill_age_days=int(restore_drill["last_drill_age_days"]),
            last_drill_succeeded=bool(restore_drill["last_drill_succeeded"]),
            files_restored=int(restore_drill["files_restored"]),
            expected_files=int(restore_drill["expected_files"]),
            hashes_match=bool(restore_drill["hashes_match"]),
            recovery_point_verified=bool(restore_drill["recovery_point_verified"]),
            structured_logs_present=bool(restore_drill["structured_logs_present"]),
            timing_metrics_present=bool(restore_drill["timing_metrics_present"]),
            data_loss_window_measured=bool(
                restore_drill["data_loss_window_measured"]
            ),
            rpo_metric_present=bool(restore_drill["rpo_metric_present"]),
            rto_metric_present=bool(restore_drill["rto_metric_present"]),
            correlation_id_present=bool(restore_drill["correlation_id_present"]),
            expected_vs_actual_diff_present=bool(
                restore_drill["expected_vs_actual_diff_present"]
            ),
            artifact_manifest_present=bool(
                restore_drill["artifact_manifest_present"]
            ),
            operator_reason_bundle_present=bool(
                restore_drill["operator_reason_bundle_present"]
            ),
            idempotent=bool(restore_drill["idempotent"]),
            safe_for_test_environments=bool(
                restore_drill["safe_for_test_environments"]
            ),
        )
    )

    objective_diagnostics = [
        evaluate_recovery_objective(
            objective.key,
            measured_data_loss_window_minutes=int(
                recovery_metrics["measured_data_loss_window_minutes"]
            ),
            measured_rto_minutes=int(recovery_metrics["measured_rto_minutes"]),
            deterministic_vendor_repull_documented=bool(
                recovery_metrics["deterministic_vendor_repull_documented"]
            ),
        )
        for objective in RECOVERY_OBJECTIVES
    ]
    diagnostics.extend(objective_diagnostics)

    readiness_inputs = {
        "backup_freshness_green": all(
            diagnostic.status == "pass"
            for diagnostic in diagnostics
            if diagnostic.control in {
                "postgres_pitr_backup",
                "off_host_durability",
                "tamper_evident_journals",
            }
        ),
        "restore_drill_green": all(
            diagnostic.status == "pass"
            for diagnostic in diagnostics
            if diagnostic.control == "restore_drill"
        ),
        "restore_evidence_green": all(
            diagnostic.status == "pass"
            for diagnostic in diagnostics
            if diagnostic.control in {
                "restore_evidence",
                "canonical_metadata_and_live_state",
                "live_capable_host",
                "raw_historical_reingestion",
            }
        ),
    }
    readiness_inputs["promotion_gate_ready"] = all(readiness_inputs.values())

    return {
        "allowed": all(diagnostic.status == "pass" for diagnostic in diagnostics),
        "recovery_objectives": [
            {
                "key": objective.key,
                "title": objective.title,
                "plan_section": objective.plan_section,
                "rpo_max_minutes": objective.rpo_max_minutes,
                "rto_max_minutes": objective.rto_max_minutes,
                "protected_assets": list(objective.protected_assets),
            }
            for objective in RECOVERY_OBJECTIVES
        ],
        "readiness_inputs": readiness_inputs,
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }
