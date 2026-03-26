"""Observability dashboards, alert classes, and operator response targets."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from typing import Any


REQUIRED_METRIC_CATEGORIES: tuple[str, ...] = (
    "release_counts_and_statuses",
    "research_funnel_counts",
    "discovery_budget_consumption",
    "portability_tradability_and_replay_pass_rates",
    "account_fit_pass_rates",
    "bar_parity_drift",
    "session_readiness_status_and_expiry",
    "live_quality_events",
    "strategy_health_drift",
    "broker_latency_and_disconnects",
    "intraday_broker_state_mismatch_counts",
    "guardian_health_and_last_emergency_drill",
    "policy_engine_latency_and_failures",
    "active_waivers_and_expiry_countdown",
    "backup_freshness_journal_digest_and_restore_drill",
    "clock_synchronization_health",
    "secret_rotation_age_and_break_glass",
    "deployment_status_counts",
)

REQUIRED_ALERT_IDS: tuple[str, ...] = (
    "open_live_position_degraded_health",
    "failed_or_stale_session_readiness_packet",
    "intraday_broker_state_mismatch",
    "backup_freshness_breach",
    "restore_drill_expiry",
    "clock_desynchronization",
    "break_glass_access",
    "emergency_flatten_unavailable",
)

REQUIRED_ALERT_CONTEXT_FIELDS: tuple[str, ...] = ("correlation_id", "reason_code")


@unique
class ObservabilityStatus(str, Enum):
    PASS = "pass"
    VIOLATION = "violation"


@unique
class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


@dataclass(frozen=True)
class DashboardSpec:
    dashboard_id: str
    title: str
    operator_goal: str
    panel_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DashboardPanelSpec:
    panel_id: str
    dashboard_id: str
    category_id: str
    title: str
    metric_keys: tuple[str, ...]
    explain_surface: str
    retained_artifact_fields: tuple[str, ...]
    freshness_fields: tuple[str, ...]
    operator_summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AlertClassSpec:
    alert_id: str
    title: str
    severity: AlertSeverity
    response_target_minutes: int
    trigger_summary: str
    related_panel_ids: tuple[str, ...]
    explain_surface: str
    required_context_fields: tuple[str, ...]
    artifact_reference_fields: tuple[str, ...]
    runbook_summary: str
    supporting_metric_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["severity"] = self.severity.value
        return payload


@dataclass(frozen=True)
class ObservabilityCoverageReport:
    status: str
    reason_code: str
    dashboard_ids: tuple[str, ...]
    panel_count: int
    alert_count: int
    missing_metric_categories: tuple[str, ...]
    missing_alert_ids: tuple[str, ...]
    dashboards_missing_panels: tuple[str, ...]
    panels_missing_explain_links: tuple[str, ...]
    panels_missing_artifact_links: tuple[str, ...]
    panels_missing_freshness_fields: tuple[str, ...]
    alerts_missing_context: tuple[str, ...]
    alerts_missing_artifact_links: tuple[str, ...]
    alerts_with_invalid_targets: tuple[str, ...]
    explanation: str
    remediation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


OBSERVABILITY_PANELS: tuple[DashboardPanelSpec, ...] = (
    DashboardPanelSpec(
        panel_id="release_status_overview",
        dashboard_id="release_pipeline",
        category_id="release_counts_and_statuses",
        title="Release counts and lifecycle status",
        metric_keys=(
            "release.active.count",
            "release.quarantined.count",
            "release.revoked.count",
        ),
        explain_surface="release_validation",
        retained_artifact_fields=("release_id", "validation_summary_hash", "certification_id"),
        freshness_fields=("certified_at_utc", "status_changed_at_utc"),
        operator_summary="Shows whether certified, suspect, and revoked release volumes are drifting.",
    ),
    DashboardPanelSpec(
        panel_id="deployment_status_overview",
        dashboard_id="release_pipeline",
        category_id="deployment_status_counts",
        title="Deployment status counts",
        metric_keys=(
            "deployment.paper_running.count",
            "deployment.shadow_running.count",
            "deployment.live_active.count",
        ),
        explain_surface="deployment_packets",
        retained_artifact_fields=("deployment_instance_id", "promotion_packet_id"),
        freshness_fields=("deployment_started_at_utc", "last_status_change_at_utc"),
        operator_summary="Keeps paper, shadow, and live deployment state visible on one board.",
    ),
    DashboardPanelSpec(
        panel_id="research_funnel_overview",
        dashboard_id="research_governance",
        category_id="research_funnel_counts",
        title="Research funnel counts",
        metric_keys=(
            "research.family.recorded.count",
            "research.family.continue.count",
            "research.family.terminate.count",
        ),
        explain_surface="research_state",
        retained_artifact_fields=("research_run_id", "family_decision_record_id"),
        freshness_fields=("created_at_utc", "revisit_at_utc"),
        operator_summary="Tracks screening volume, continuation, and termination flow.",
    ),
    DashboardPanelSpec(
        panel_id="discovery_budget_burn",
        dashboard_id="research_governance",
        category_id="discovery_budget_consumption",
        title="Discovery budget consumption",
        metric_keys=(
            "research.discovery_budget.authorized_usd",
            "research.discovery_budget.consumed_usd",
        ),
        explain_surface="research_state",
        retained_artifact_fields=("family_decision_record_id", "policy_bundle_hash"),
        freshness_fields=("created_at_utc", "revisit_at_utc"),
        operator_summary="Shows whether discovery burn is still aligned with decision cadence.",
    ),
    DashboardPanelSpec(
        panel_id="portability_replay_quality",
        dashboard_id="research_governance",
        category_id="portability_tradability_and_replay_pass_rates",
        title="Portability, tradability, and replay pass rates",
        metric_keys=(
            "research.portability.pass_rate",
            "research.tradability.pass_rate",
            "research.replay.pass_rate",
        ),
        explain_surface="research_state",
        retained_artifact_fields=("research_run_id", "candidate_bundle_id"),
        freshness_fields=("recorded_at_utc", "certified_at_utc"),
        operator_summary="Shows whether promotable research is surviving portability, tradability, and replay gates.",
    ),
    DashboardPanelSpec(
        panel_id="account_fit_summary",
        dashboard_id="research_governance",
        category_id="account_fit_pass_rates",
        title="Account-fit pass rates",
        metric_keys=("research.account_fit.pass_rate",),
        explain_surface="deployment_packets",
        retained_artifact_fields=("candidate_bundle_id", "target_account_binding_id"),
        freshness_fields=("evaluated_at_utc", "valid_to_utc"),
        operator_summary="Makes account-class eligibility failures visible before readiness work starts.",
    ),
    DashboardPanelSpec(
        panel_id="bar_parity_drift_summary",
        dashboard_id="readiness_and_policy",
        category_id="bar_parity_drift",
        title="Bar-parity drift",
        metric_keys=(
            "parity.ohlcv.mismatch_rate",
            "parity.anchor_timing.mismatch_rate",
            "parity.availability.mismatch_rate",
        ),
        explain_surface="parity_certification",
        retained_artifact_fields=("parity_artifact_id", "data_profile_release_id"),
        freshness_fields=("certified_at_utc", "expires_at_utc"),
        operator_summary="Keeps Databento-to-IBKR bar drift freshness-bound rather than assumed.",
    ),
    DashboardPanelSpec(
        panel_id="session_readiness_window",
        dashboard_id="readiness_and_policy",
        category_id="session_readiness_status_and_expiry",
        title="Session-readiness status and expiry windows",
        metric_keys=(
            "session_readiness.green.count",
            "session_readiness.blocked.count",
            "session_readiness.expiring_within_15m.count",
        ),
        explain_surface="deployment_packets",
        retained_artifact_fields=("session_readiness_packet_id", "promotion_packet_id"),
        freshness_fields=("valid_from_utc", "valid_to_utc"),
        operator_summary="Shows readiness status plus time-to-expiry so the operator can act before the window closes.",
    ),
    DashboardPanelSpec(
        panel_id="policy_engine_health",
        dashboard_id="readiness_and_policy",
        category_id="policy_engine_latency_and_failures",
        title="Policy-engine latency and failures",
        metric_keys=(
            "policy_engine.decision_latency_p95_ms",
            "policy_engine.blocked_decision.count",
            "policy_engine.invalid_input.count",
        ),
        explain_surface="policy_engine",
        retained_artifact_fields=("decision_id", "policy_bundle_hash", "waiver_id"),
        freshness_fields=("decided_at_utc", "waiver_expires_at_utc"),
        operator_summary="Tracks whether the policy engine is timely and whether decisions are degrading.",
    ),
    DashboardPanelSpec(
        panel_id="waiver_expiry_countdown",
        dashboard_id="readiness_and_policy",
        category_id="active_waivers_and_expiry_countdown",
        title="Active waivers and expiry countdowns",
        metric_keys=(
            "policy_engine.active_waiver.count",
            "policy_engine.waiver_expiring_within_24h.count",
        ),
        explain_surface="policy_engine",
        retained_artifact_fields=("waiver_id", "related_incident_id"),
        freshness_fields=("approved_at_utc", "expires_at_utc"),
        operator_summary="Prevents temporary waivers from silently becoming permanent operating posture.",
    ),
    DashboardPanelSpec(
        panel_id="live_quality_events",
        dashboard_id="live_operations",
        category_id="live_quality_events",
        title="Live quality events",
        metric_keys=(
            "runtime.quality_event.count",
            "runtime.quality_event.open.count",
        ),
        explain_surface="runtime_quality",
        retained_artifact_fields=("deployment_instance_id", "correlation_id"),
        freshness_fields=("recorded_at_utc", "last_event_at_utc"),
        operator_summary="Shows open live quality incidents and fresh event volume.",
    ),
    DashboardPanelSpec(
        panel_id="strategy_health_drift",
        dashboard_id="live_operations",
        category_id="strategy_health_drift",
        title="Strategy-health drift",
        metric_keys=(
            "runtime.strategy_health.drift_score",
            "runtime.strategy_health.degraded.count",
        ),
        explain_surface="policy_engine",
        retained_artifact_fields=("candidate_bundle_id", "deployment_instance_id"),
        freshness_fields=("measured_at_utc", "session_readiness_valid_to_utc"),
        operator_summary="Highlights when a deployed strategy has drifted outside its approved operating envelope.",
    ),
    DashboardPanelSpec(
        panel_id="broker_connectivity",
        dashboard_id="live_operations",
        category_id="broker_latency_and_disconnects",
        title="Broker latency and disconnects",
        metric_keys=(
            "broker.submit_to_ack.p95_ms",
            "broker.disconnect.count",
        ),
        explain_surface="broker_connectivity",
        retained_artifact_fields=("deployment_instance_id", "broker_session_id"),
        freshness_fields=("measured_at_utc", "last_disconnect_at_utc"),
        operator_summary="Makes broker instability visible before it compounds into unsafe live behavior.",
    ),
    DashboardPanelSpec(
        panel_id="broker_state_mismatch",
        dashboard_id="live_operations",
        category_id="intraday_broker_state_mismatch_counts",
        title="Intraday broker-state mismatch counts",
        metric_keys=(
            "broker_state_mismatch.open.count",
            "broker_state_mismatch.escalated.count",
        ),
        explain_surface="accounting_ledger",
        retained_artifact_fields=("deployment_instance_id", "order_intent_id", "ledger_close_artifact_id"),
        freshness_fields=("detected_at_utc", "last_reconciled_at_utc"),
        operator_summary="Tracks unresolved broker-state divergence before it becomes a live safety incident.",
    ),
    DashboardPanelSpec(
        panel_id="guardian_health",
        dashboard_id="live_operations",
        category_id="guardian_health_and_last_emergency_drill",
        title="Guardian health and last emergency drill",
        metric_keys=(
            "guardian.health.green",
            "guardian.emergency_drill.age_minutes",
        ),
        explain_surface="guardian_path",
        retained_artifact_fields=("guardian_check_id", "last_emergency_drill_id"),
        freshness_fields=("checked_at_utc", "last_emergency_drill_at_utc"),
        operator_summary="Shows whether emergency control is healthy and when it was last drilled.",
    ),
    DashboardPanelSpec(
        panel_id="recovery_evidence_health",
        dashboard_id="recovery_and_security",
        category_id="backup_freshness_journal_digest_and_restore_drill",
        title="Backup freshness, journal digest, and restore-drill status",
        metric_keys=(
            "recovery.backup_freshness.green",
            "recovery.journal_digest.verified",
            "recovery.restore_drill.age_days",
        ),
        explain_surface="durability",
        retained_artifact_fields=("manifest_id", "artifact_checkpoint_id", "decision_trace_id"),
        freshness_fields=("generated_at_utc", "last_restore_drill_at_utc"),
        operator_summary="Keeps durability evidence fresh enough for real recovery, not just documentation.",
    ),
    DashboardPanelSpec(
        panel_id="clock_sync_health",
        dashboard_id="recovery_and_security",
        category_id="clock_synchronization_health",
        title="Clock-synchronization health",
        metric_keys=(
            "clock.skew.ms",
            "clock.sync_unknown.count",
        ),
        explain_surface="clock_discipline",
        retained_artifact_fields=("clock_health_check_id", "session_id"),
        freshness_fields=("measured_at_utc", "session_boundary_resolved_at_utc"),
        operator_summary="Shows whether synchronization is still trustworthy for readiness and live operation.",
    ),
    DashboardPanelSpec(
        panel_id="secret_and_break_glass",
        dashboard_id="recovery_and_security",
        category_id="secret_rotation_age_and_break_glass",
        title="Secret rotation age and break-glass events",
        metric_keys=(
            "security.secret_rotation.age_days",
            "security.break_glass.count",
        ),
        explain_surface="trust_zones",
        retained_artifact_fields=("incident_review_record_id", "credential_ref"),
        freshness_fields=("rotated_at_utc", "last_break_glass_at_utc"),
        operator_summary="Shows aging secrets and emergency access events on the same security surface.",
    ),
)


OBSERVABILITY_DASHBOARDS: tuple[DashboardSpec, ...] = (
    DashboardSpec(
        dashboard_id="release_pipeline",
        title="Release pipeline and deployment posture",
        operator_goal="Track release health and deployment state before runtime promotion.",
        panel_ids=("release_status_overview", "deployment_status_overview"),
    ),
    DashboardSpec(
        dashboard_id="research_governance",
        title="Research governance and selection",
        operator_goal="Track funnel health, budget burn, and candidate survival.",
        panel_ids=(
            "research_funnel_overview",
            "discovery_budget_burn",
            "portability_replay_quality",
            "account_fit_summary",
        ),
    ),
    DashboardSpec(
        dashboard_id="readiness_and_policy",
        title="Readiness and policy evidence",
        operator_goal="Watch parity, readiness expiry, policy latency, and waiver freshness.",
        panel_ids=(
            "bar_parity_drift_summary",
            "session_readiness_window",
            "policy_engine_health",
            "waiver_expiry_countdown",
        ),
    ),
    DashboardSpec(
        dashboard_id="live_operations",
        title="Live operations and emergency path",
        operator_goal="See live degradation, broker instability, mismatches, and emergency-path readiness early.",
        panel_ids=(
            "live_quality_events",
            "strategy_health_drift",
            "broker_connectivity",
            "broker_state_mismatch",
            "guardian_health",
        ),
    ),
    DashboardSpec(
        dashboard_id="recovery_and_security",
        title="Recovery, clock, and security controls",
        operator_goal="Keep recovery evidence, synchronization, and break-glass controls visible.",
        panel_ids=(
            "recovery_evidence_health",
            "clock_sync_health",
            "secret_and_break_glass",
        ),
    ),
)


OBSERVABILITY_ALERTS: tuple[AlertClassSpec, ...] = (
    AlertClassSpec(
        alert_id="open_live_position_degraded_health",
        title="Open live position with degraded health",
        severity=AlertSeverity.CRITICAL,
        response_target_minutes=1,
        trigger_summary="Trigger when live exposure remains open while strategy or runtime health is degraded.",
        related_panel_ids=("live_quality_events", "strategy_health_drift"),
        explain_surface="policy_engine",
        required_context_fields=(
            "correlation_id",
            "reason_code",
            "deployment_instance_id",
            "candidate_bundle_id",
            "open_position_count",
        ),
        artifact_reference_fields=("decision_trace_id", "session_readiness_packet_id"),
        runbook_summary="Review the live deployment trace, confirm safe flatten capability, and stop new entries immediately.",
        supporting_metric_keys=(
            "runtime.quality_event.open.count",
            "runtime.strategy_health.degraded.count",
        ),
    ),
    AlertClassSpec(
        alert_id="failed_or_stale_session_readiness_packet",
        title="Failed or stale session-readiness packet",
        severity=AlertSeverity.CRITICAL,
        response_target_minutes=2,
        trigger_summary="Trigger when the readiness packet blocks, expires, or is nearing expiry without renewal.",
        related_panel_ids=("session_readiness_window",),
        explain_surface="deployment_packets",
        required_context_fields=(
            "correlation_id",
            "reason_code",
            "session_readiness_packet_id",
            "valid_to_utc",
            "blocked_check_ids",
        ),
        artifact_reference_fields=("promotion_packet_id", "decision_trace_hash"),
        runbook_summary="Stop activation or new entries, inspect blocked checks, and either refresh or revoke the readiness packet.",
        supporting_metric_keys=(
            "session_readiness.blocked.count",
            "session_readiness.expiring_within_15m.count",
        ),
    ),
    AlertClassSpec(
        alert_id="intraday_broker_state_mismatch",
        title="Intraday broker-state mismatch",
        severity=AlertSeverity.CRITICAL,
        response_target_minutes=2,
        trigger_summary="Trigger when the broker reports live state that does not reconcile with the canonical ledger.",
        related_panel_ids=("broker_state_mismatch",),
        explain_surface="accounting_ledger",
        required_context_fields=(
            "correlation_id",
            "reason_code",
            "deployment_instance_id",
            "broker_snapshot_id",
            "mismatch_count",
        ),
        artifact_reference_fields=("order_intent_id", "ledger_close_artifact_id"),
        runbook_summary="Freeze new orders, reconcile positions and open intents, then escalate if the mismatch persists.",
        supporting_metric_keys=(
            "broker_state_mismatch.open.count",
            "broker_state_mismatch.escalated.count",
        ),
    ),
    AlertClassSpec(
        alert_id="backup_freshness_breach",
        title="Backup freshness breach",
        severity=AlertSeverity.HIGH,
        response_target_minutes=10,
        trigger_summary="Trigger when canonical backup freshness or PITR lag leaves the approved RPO window.",
        related_panel_ids=("recovery_evidence_health",),
        explain_surface="durability",
        required_context_fields=(
            "correlation_id",
            "reason_code",
            "manifest_id",
            "recovery_point_lag_minutes",
        ),
        artifact_reference_fields=("artifact_checkpoint_id", "database_backup_label"),
        runbook_summary="Restore backup freshness before approving further live operation or readiness packets.",
        supporting_metric_keys=(
            "recovery.backup_freshness.green",
            "recovery.restore_drill.age_days",
        ),
    ),
    AlertClassSpec(
        alert_id="restore_drill_expiry",
        title="Restore-drill expiry",
        severity=AlertSeverity.HIGH,
        response_target_minutes=60,
        trigger_summary="Trigger when restore-drill evidence ages past the approved refresh window.",
        related_panel_ids=("recovery_evidence_health", "guardian_health"),
        explain_surface="durability",
        required_context_fields=(
            "correlation_id",
            "reason_code",
            "manifest_id",
            "last_restore_drill_at_utc",
        ),
        artifact_reference_fields=("decision_trace_id", "artifact_checkpoint_id"),
        runbook_summary="Schedule and execute a fresh restore drill before treating recovery evidence as current.",
        supporting_metric_keys=("recovery.restore_drill.age_days",),
    ),
    AlertClassSpec(
        alert_id="clock_desynchronization",
        title="Clock desynchronization",
        severity=AlertSeverity.CRITICAL,
        response_target_minutes=1,
        trigger_summary="Trigger when synchronization becomes unknown or skew exceeds the approved threshold.",
        related_panel_ids=("clock_sync_health",),
        explain_surface="clock_discipline",
        required_context_fields=(
            "correlation_id",
            "reason_code",
            "measured_skew_ms",
            "configured_threshold_ms",
        ),
        artifact_reference_fields=("clock_health_check_id",),
        runbook_summary="Block new entries, restore trusted synchronization, and review session-boundary effects before resuming.",
        supporting_metric_keys=("clock.skew.ms", "clock.sync_unknown.count"),
    ),
    AlertClassSpec(
        alert_id="break_glass_access",
        title="Break-glass access",
        severity=AlertSeverity.HIGH,
        response_target_minutes=5,
        trigger_summary="Trigger on any break-glass credential use or emergency access escalation.",
        related_panel_ids=("secret_and_break_glass",),
        explain_surface="trust_zones",
        required_context_fields=(
            "correlation_id",
            "reason_code",
            "incident_review_record_id",
            "credential_ref",
        ),
        artifact_reference_fields=("incident_review_record_id", "credential_ref"),
        runbook_summary="Open an incident review, verify scope and duration, and rotate credentials if needed.",
        supporting_metric_keys=("security.break_glass.count",),
    ),
    AlertClassSpec(
        alert_id="emergency_flatten_unavailable",
        title="Inability to execute emergency flatten",
        severity=AlertSeverity.CRITICAL,
        response_target_minutes=1,
        trigger_summary="Trigger when the independent guardian path or flatten control is unavailable.",
        related_panel_ids=("guardian_health", "broker_connectivity"),
        explain_surface="guardian_path",
        required_context_fields=(
            "correlation_id",
            "reason_code",
            "deployment_instance_id",
            "guardian_check_id",
        ),
        artifact_reference_fields=("last_emergency_drill_id", "decision_trace_id"),
        runbook_summary="Escalate immediately, halt new risk, and recover independent flatten capability before proceeding.",
        supporting_metric_keys=("guardian.health.green", "broker.disconnect.count"),
    ),
)


def dashboard_ids() -> list[str]:
    return sorted(dashboard.dashboard_id for dashboard in OBSERVABILITY_DASHBOARDS)


def alert_ids() -> list[str]:
    return sorted(alert.alert_id for alert in OBSERVABILITY_ALERTS)


def _validate_catalog() -> list[str]:
    errors: list[str] = []
    panel_ids = {panel.panel_id for panel in OBSERVABILITY_PANELS}
    category_ids = {panel.category_id for panel in OBSERVABILITY_PANELS}
    dashboard_id_set = {dashboard.dashboard_id for dashboard in OBSERVABILITY_DASHBOARDS}

    missing_categories = set(REQUIRED_METRIC_CATEGORIES).difference(category_ids)
    if missing_categories:
        errors.append(
            "observability panels are missing required categories: "
            + ", ".join(sorted(missing_categories))
        )

    missing_alerts = set(REQUIRED_ALERT_IDS).difference(alert_ids())
    if missing_alerts:
        errors.append(
            "observability alerts are missing required alert classes: "
            + ", ".join(sorted(missing_alerts))
        )

    for dashboard in OBSERVABILITY_DASHBOARDS:
        if not dashboard.panel_ids:
            errors.append(f"{dashboard.dashboard_id}: dashboard must include at least one panel")
        for panel_id in dashboard.panel_ids:
            if panel_id not in panel_ids:
                errors.append(f"{dashboard.dashboard_id}: unknown panel {panel_id}")

    for panel in OBSERVABILITY_PANELS:
        if panel.dashboard_id not in dashboard_id_set:
            errors.append(f"{panel.panel_id}: unknown dashboard {panel.dashboard_id}")
        if not panel.metric_keys:
            errors.append(f"{panel.panel_id}: panel must declare at least one metric")
        if not panel.explain_surface:
            errors.append(f"{panel.panel_id}: explain surface is required")
        if not panel.retained_artifact_fields:
            errors.append(f"{panel.panel_id}: retained artifact links are required")
        if not panel.freshness_fields:
            errors.append(f"{panel.panel_id}: freshness fields are required")

    for alert in OBSERVABILITY_ALERTS:
        if alert.response_target_minutes <= 0:
            errors.append(f"{alert.alert_id}: response target must be positive")
        if not set(REQUIRED_ALERT_CONTEXT_FIELDS).issubset(alert.required_context_fields):
            errors.append(
                f"{alert.alert_id}: required context fields must include correlation_id and reason_code"
            )
        if not alert.artifact_reference_fields:
            errors.append(f"{alert.alert_id}: alert must link retained artifacts")
        if not alert.supporting_metric_keys:
            errors.append(f"{alert.alert_id}: alert must link supporting metrics")
        if not alert.explain_surface:
            errors.append(f"{alert.alert_id}: alert must link an explain surface")
        for panel_id in alert.related_panel_ids:
            if panel_id not in panel_ids:
                errors.append(f"{alert.alert_id}: unknown related panel {panel_id}")

    return errors


VALIDATION_ERRORS = _validate_catalog()


def evaluate_observability_coverage(
    *,
    dashboards: tuple[DashboardSpec, ...] = OBSERVABILITY_DASHBOARDS,
    panels: tuple[DashboardPanelSpec, ...] = OBSERVABILITY_PANELS,
    alerts: tuple[AlertClassSpec, ...] = OBSERVABILITY_ALERTS,
) -> ObservabilityCoverageReport:
    dashboard_set = {dashboard.dashboard_id for dashboard in dashboards}
    panel_ids_by_dashboard = {
        dashboard.dashboard_id: set(dashboard.panel_ids) for dashboard in dashboards
    }
    observed_categories = {panel.category_id for panel in panels}
    observed_alerts = {alert.alert_id for alert in alerts}

    missing_metric_categories = tuple(
        sorted(set(REQUIRED_METRIC_CATEGORIES).difference(observed_categories))
    )
    missing_alert_ids = tuple(sorted(set(REQUIRED_ALERT_IDS).difference(observed_alerts)))
    dashboards_missing_panels = tuple(
        sorted(
            dashboard.dashboard_id
            for dashboard in dashboards
            if not panel_ids_by_dashboard[dashboard.dashboard_id]
        )
    )
    panels_missing_explain_links = tuple(
        sorted(panel.panel_id for panel in panels if not panel.explain_surface)
    )
    panels_missing_artifact_links = tuple(
        sorted(panel.panel_id for panel in panels if not panel.retained_artifact_fields)
    )
    panels_missing_freshness_fields = tuple(
        sorted(panel.panel_id for panel in panels if not panel.freshness_fields)
    )
    alerts_missing_context = tuple(
        sorted(
            alert.alert_id
            for alert in alerts
            if not set(REQUIRED_ALERT_CONTEXT_FIELDS).issubset(alert.required_context_fields)
        )
    )
    alerts_missing_artifact_links = tuple(
        sorted(alert.alert_id for alert in alerts if not alert.artifact_reference_fields)
    )
    alerts_with_invalid_targets = tuple(
        sorted(alert.alert_id for alert in alerts if alert.response_target_minutes <= 0)
    )

    unknown_dashboard_references = tuple(
        sorted(panel.panel_id for panel in panels if panel.dashboard_id not in dashboard_set)
    )
    if unknown_dashboard_references:
        panels_missing_explain_links = tuple(
            sorted(set(panels_missing_explain_links).union(unknown_dashboard_references))
        )

    if (
        missing_metric_categories
        or missing_alert_ids
        or dashboards_missing_panels
        or panels_missing_explain_links
        or panels_missing_artifact_links
        or panels_missing_freshness_fields
        or alerts_missing_context
        or alerts_missing_artifact_links
        or alerts_with_invalid_targets
    ):
        return ObservabilityCoverageReport(
            status=ObservabilityStatus.VIOLATION.value,
            reason_code="OBSERVABILITY_COVERAGE_INCOMPLETE",
            dashboard_ids=tuple(sorted(dashboard_set)),
            panel_count=len(panels),
            alert_count=len(alerts),
            missing_metric_categories=missing_metric_categories,
            missing_alert_ids=missing_alert_ids,
            dashboards_missing_panels=dashboards_missing_panels,
            panels_missing_explain_links=panels_missing_explain_links,
            panels_missing_artifact_links=panels_missing_artifact_links,
            panels_missing_freshness_fields=panels_missing_freshness_fields,
            alerts_missing_context=alerts_missing_context,
            alerts_missing_artifact_links=alerts_missing_artifact_links,
            alerts_with_invalid_targets=alerts_with_invalid_targets,
            explanation=(
                "Observability coverage is incomplete, so the operator would lose either alert "
                "context, freshness visibility, or artifact links."
            ),
            remediation=(
                "Populate the missing categories, link each alert to explain surfaces and retained "
                "artifacts, and keep freshness fields visible on every dashboard panel."
            ),
        )

    return ObservabilityCoverageReport(
        status=ObservabilityStatus.PASS.value,
        reason_code="OBSERVABILITY_COVERAGE_COMPLETE",
        dashboard_ids=tuple(sorted(dashboard_set)),
        panel_count=len(panels),
        alert_count=len(alerts),
        missing_metric_categories=(),
        missing_alert_ids=(),
        dashboards_missing_panels=(),
        panels_missing_explain_links=(),
        panels_missing_artifact_links=(),
        panels_missing_freshness_fields=(),
        alerts_missing_context=(),
        alerts_missing_artifact_links=(),
        alerts_with_invalid_targets=(),
        explanation=(
            "Dashboards and alerts cover the required categories, response targets, freshness "
            "windows, explain surfaces, and retained-artifact links."
        ),
        remediation="Keep dashboard categories and alert response targets aligned with policy changes.",
    )
