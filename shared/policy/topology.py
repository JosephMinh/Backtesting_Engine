"""One-host baseline topology contract and startup health checks."""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from shared.policy.tiers import evaluate_all_upgrade_triggers, one_host_baseline_holds


@dataclass(frozen=True)
class BaselineComponent:
    key: str
    title: str
    role: str
    plan_section: str
    expected_location: str
    dependencies: tuple[str, ...]
    resolution_guidance: str


@dataclass(frozen=True)
class TopologyDiagnostic:
    component: str
    title: str
    status: str
    reason_code: str | None
    plan_section: str
    dependency_status: dict[str, str]
    diagnostic_context: dict[str, Any]
    resolution_guidance: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


BASELINE_COMPONENTS: tuple[BaselineComponent, ...] = (
    BaselineComponent(
        key="linux_host",
        title="One Linux host or VM",
        role="Single production-capable host for the approved v1 lane",
        plan_section="3.2",
        expected_location="on_host",
        dependencies=(),
        resolution_guidance="Provision exactly one Linux host or VM for the approved hot path.",
    ),
    BaselineComponent(
        key="postgresql16",
        title="PostgreSQL 16",
        role="Canonical metadata and v1 telemetry store",
        plan_section="3.2",
        expected_location="on_host",
        dependencies=("linux_host",),
        resolution_guidance="Run PostgreSQL 16 on the one-host baseline before declaring startup healthy.",
    ),
    BaselineComponent(
        key="off_host_object_storage",
        title="Off-host versioned object storage",
        role="Immutable artifacts, backups, and journals",
        plan_section="3.2",
        expected_location="off_host",
        dependencies=(),
        resolution_guidance="Provide versioned off-host object storage for immutable artifacts and durability evidence.",
    ),
    BaselineComponent(
        key="prometheus",
        title="Prometheus",
        role="Metrics collection for the one-host stack",
        plan_section="3.2",
        expected_location="on_host",
        dependencies=("linux_host",),
        resolution_guidance="Expose Prometheus so baseline services publish startup and runtime health.",
    ),
    BaselineComponent(
        key="grafana",
        title="Grafana",
        role="Operator dashboards for baseline observability",
        plan_section="3.2",
        expected_location="on_host",
        dependencies=("linux_host", "prometheus", "loki"),
        resolution_guidance="Provide Grafana with healthy metrics and log backends before calling observability green.",
    ),
    BaselineComponent(
        key="loki",
        title="Loki",
        role="Structured log storage for observability",
        plan_section="3.2",
        expected_location="on_host",
        dependencies=("linux_host",),
        resolution_guidance="Provide Loki so structured logs remain queryable during startup and incidents.",
    ),
    BaselineComponent(
        key="ib_gateway",
        title="IB Gateway or TWS",
        role="Supervised broker connectivity on the same host",
        plan_section="3.2",
        expected_location="on_host",
        dependencies=("linux_host",),
        resolution_guidance="Run IB Gateway or TWS under supervision on the one-host baseline.",
    ),
    BaselineComponent(
        key="opsd",
        title="opsd",
        role="Primary operational daemon",
        plan_section="3.2",
        expected_location="on_host",
        dependencies=("linux_host", "postgresql16", "off_host_object_storage", "ib_gateway"),
        resolution_guidance="Keep opsd dependent on healthy metadata, durability, and broker services before startup passes.",
    ),
    BaselineComponent(
        key="guardian",
        title="guardian",
        role="Independent out-of-band emergency control process",
        plan_section="3.2",
        expected_location="on_host",
        dependencies=("linux_host", "ib_gateway"),
        resolution_guidance="Run guardian separately from opsd so emergency cancel/flatten remains independently available.",
    ),
    BaselineComponent(
        key="watchdog",
        title="Watchdog or supervisor",
        role="Supervises opsd, guardian, and broker gateway",
        plan_section="3.2",
        expected_location="on_host",
        dependencies=("linux_host", "opsd", "guardian", "ib_gateway"),
        resolution_guidance="Run a small watchdog or supervisor over opsd, guardian, and the broker gateway.",
    ),
)

_COMPONENT_INDEX: dict[str, BaselineComponent] = {
    component.key: component for component in BASELINE_COMPONENTS
}


def baseline_component_keys() -> list[str]:
    return [component.key for component in BASELINE_COMPONENTS]


def _component_state(
    component_key: str, component_status: dict[str, dict[str, Any]]
) -> str:
    status = component_status.get(component_key, {})
    if not status.get("present", False):
        return "missing"
    if not status.get("connectable", False):
        return "not_connectable"
    if not status.get("healthy", False):
        return "unhealthy"
    return "healthy"


def evaluate_component_startup(
    component_key: str,
    component_status: dict[str, dict[str, Any]],
) -> TopologyDiagnostic:
    component = _COMPONENT_INDEX[component_key]
    status = component_status.get(component_key, {})
    dependency_status = {
        dependency: _component_state(dependency, component_status)
        for dependency in component.dependencies
    }
    diagnostic_context = {
        "present": status.get("present", False),
        "connectable": status.get("connectable", False),
        "healthy": status.get("healthy", False),
        "expected_location": component.expected_location,
    }

    if not status.get("present", False):
        return TopologyDiagnostic(
            component=component.key,
            title=component.title,
            status="violation",
            reason_code=f"TOPOLOGY_COMPONENT_MISSING_{component.key.upper()}",
            plan_section=component.plan_section,
            dependency_status=dependency_status,
            diagnostic_context=diagnostic_context,
            resolution_guidance=component.resolution_guidance,
            explanation=f"{component.title} is required for the one-host baseline but is not present.",
        )

    unhealthy_dependencies = {
        key: value for key, value in dependency_status.items() if value != "healthy"
    }
    if unhealthy_dependencies:
        return TopologyDiagnostic(
            component=component.key,
            title=component.title,
            status="violation",
            reason_code=f"TOPOLOGY_DEPENDENCY_UNHEALTHY_{component.key.upper()}",
            plan_section=component.plan_section,
            dependency_status=dependency_status,
            diagnostic_context=diagnostic_context,
            resolution_guidance=component.resolution_guidance,
            explanation=(
                f"{component.title} depends on healthy upstream components before startup passes: "
                f"{unhealthy_dependencies}."
            ),
        )

    if not status.get("connectable", False):
        return TopologyDiagnostic(
            component=component.key,
            title=component.title,
            status="violation",
            reason_code=f"TOPOLOGY_COMPONENT_NOT_CONNECTABLE_{component.key.upper()}",
            plan_section=component.plan_section,
            dependency_status=dependency_status,
            diagnostic_context=diagnostic_context,
            resolution_guidance=component.resolution_guidance,
            explanation=f"{component.title} is present but not connectable from the one-host stack.",
        )

    if not status.get("healthy", False):
        return TopologyDiagnostic(
            component=component.key,
            title=component.title,
            status="violation",
            reason_code=f"TOPOLOGY_COMPONENT_UNHEALTHY_{component.key.upper()}",
            plan_section=component.plan_section,
            dependency_status=dependency_status,
            diagnostic_context=diagnostic_context,
            resolution_guidance=component.resolution_guidance,
            explanation=f"{component.title} is present and connectable but not reporting healthy.",
        )

    return TopologyDiagnostic(
        component=component.key,
        title=component.title,
        status="pass",
        reason_code=None,
        plan_section=component.plan_section,
        dependency_status=dependency_status,
        diagnostic_context=diagnostic_context,
        resolution_guidance=component.resolution_guidance,
        explanation=f"{component.title} is present, connectable, and healthy.",
    )


def evaluate_startup_checks(
    component_status: dict[str, dict[str, Any]]
) -> list[TopologyDiagnostic]:
    return [
        evaluate_component_startup(component.key, component_status)
        for component in BASELINE_COMPONENTS
    ]


def evaluate_topology(
    *,
    host_count: int,
    component_status: dict[str, dict[str, Any]],
    upgrade_trigger_evidence: dict[str, Any],
) -> dict[str, Any]:
    startup_diagnostics = evaluate_startup_checks(component_status)
    trigger_diagnostics = [trace.to_dict() for trace in evaluate_all_upgrade_triggers(upgrade_trigger_evidence)]
    baseline_holds = one_host_baseline_holds(upgrade_trigger_evidence)
    host_count_ok = host_count == 1

    if host_count_ok and baseline_holds:
        baseline_trace = TopologyDiagnostic(
            component="one_host_baseline",
            title="One-host baseline sufficiency",
            status="pass",
            reason_code=None,
            plan_section="3.2",
            dependency_status={},
            diagnostic_context={
                "host_count": host_count,
                "upgrade_trigger_evidence": upgrade_trigger_evidence,
            },
            resolution_guidance="Stay on the one-host baseline until an explicit upgrade trigger fires.",
            explanation="The one-host baseline remains sufficient because host count is one and no upgrade trigger is active.",
        )
    else:
        baseline_trace = TopologyDiagnostic(
            component="one_host_baseline",
            title="One-host baseline sufficiency",
            status="violation",
            reason_code="TOPOLOGY_ONE_HOST_BASELINE_NO_LONGER_SUFFICIENT",
            plan_section="3.2",
            dependency_status={},
            diagnostic_context={
                "host_count": host_count,
                "upgrade_trigger_evidence": upgrade_trigger_evidence,
            },
            resolution_guidance="Do not treat the one-host topology as sufficient once host count drifts or an upgrade trigger becomes active.",
            explanation="The one-host baseline is no longer sufficient because host count drifted or an upgrade trigger fired.",
        )

    allowed = (
        baseline_trace.status == "pass"
        and all(diagnostic.status == "pass" for diagnostic in startup_diagnostics)
    )

    return {
        "allowed": allowed,
        "baseline_trace": baseline_trace.to_dict(),
        "startup_diagnostics": [diagnostic.to_dict() for diagnostic in startup_diagnostics],
        "upgrade_triggers": trigger_diagnostics,
    }
