"""Trust-zone isolation, secret-delivery, and break-glass policy contracts."""

from __future__ import annotations

import datetime
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TrustZone:
    zone_id: str
    title: str
    plan_section: str
    allowed_workloads: tuple[str, ...]
    allowed_secret_types: tuple[str, ...]
    resolution_guidance: str


@dataclass(frozen=True)
class SecretDeliverySurface:
    surface: str
    title: str
    plan_section: str
    embedded: bool
    baseline_supported: bool
    conditional_only: bool
    requires_root_only_permissions: bool
    resolution_guidance: str


@dataclass(frozen=True)
class TrustZoneDiagnostic:
    zone: str
    status: str
    reason_code: str | None
    plan_section: str
    boundary_crossed: str
    surface: str
    secret_type: str | None
    expected_control: str
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


TRUST_ZONES: tuple[TrustZone, ...] = (
    TrustZone(
        zone_id="research",
        title="Research",
        plan_section="3.4",
        allowed_workloads=("notebook", "experiment", "tuning_job", "reporting"),
        allowed_secret_types=("research_credential",),
        resolution_guidance=(
            "Keep research limited to notebooks, experiments, tuning, and "
            "reporting with research-only credentials."
        ),
    ),
    TrustZone(
        zone_id="release",
        title="Release and certification",
        plan_section="3.4",
        allowed_workloads=(
            "artifact_publication",
            "signed_promotion_tooling",
            "certification",
        ),
        allowed_secret_types=("release_credential", "release_signing_key"),
        resolution_guidance=(
            "Keep release surfaces limited to certification and signed artifact "
            "promotion with release-only credentials."
        ),
    ),
    TrustZone(
        zone_id="operations",
        title="Paper, shadow, and live operations",
        plan_section="3.4",
        allowed_workloads=(
            "opsd",
            "broker_connectivity",
            "reconciliation",
            "live_control",
        ),
        allowed_secret_types=(
            "operations_runtime_credential",
            "broker_runtime_credential",
            "storage_prefix_credential",
        ),
        resolution_guidance=(
            "Keep the operational zone limited to supervised runtime services "
            "and least-privilege operational credentials."
        ),
    ),
)


SECRET_DELIVERY_SURFACES: tuple[SecretDeliverySurface, ...] = (
    SecretDeliverySurface(
        surface="runtime_secret_path",
        title="Controlled runtime secret path",
        plan_section="3.7",
        embedded=False,
        baseline_supported=True,
        conditional_only=False,
        requires_root_only_permissions=False,
        resolution_guidance=(
            "Inject runtime secrets from controlled secret paths instead of "
            "embedding them in manifests or unit files."
        ),
    ),
    SecretDeliverySurface(
        surface="root_only_encrypted_file",
        title="Encrypted root-only on-disk secret",
        plan_section="3.7",
        embedded=False,
        baseline_supported=True,
        conditional_only=False,
        requires_root_only_permissions=True,
        resolution_guidance=(
            "Keep encrypted on-disk secrets root-only when using the one-host "
            "baseline."
        ),
    ),
    SecretDeliverySurface(
        surface="secret_service",
        title="Dedicated secret-management service",
        plan_section="3.7",
        embedded=False,
        baseline_supported=True,
        conditional_only=True,
        requires_root_only_permissions=False,
        resolution_guidance=(
            "Use a heavier secret-management service once credential domains "
            "grow beyond the simple baseline."
        ),
    ),
    SecretDeliverySurface(
        surface="source_code",
        title="Source code",
        plan_section="3.7",
        embedded=True,
        baseline_supported=False,
        conditional_only=False,
        requires_root_only_permissions=False,
        resolution_guidance="Remove credentials from source control immediately.",
    ),
    SecretDeliverySurface(
        surface="notebook",
        title="Notebook",
        plan_section="3.7",
        embedded=True,
        baseline_supported=False,
        conditional_only=False,
        requires_root_only_permissions=False,
        resolution_guidance="Do not place operational credentials in notebooks.",
    ),
    SecretDeliverySurface(
        surface="manifest",
        title="Manifest",
        plan_section="3.7",
        embedded=True,
        baseline_supported=False,
        conditional_only=False,
        requires_root_only_permissions=False,
        resolution_guidance="Inject secrets at runtime rather than embedding them in manifests.",
    ),
    SecretDeliverySurface(
        surface="candidate_bundle",
        title="Candidate bundle",
        plan_section="3.7",
        embedded=True,
        baseline_supported=False,
        conditional_only=False,
        requires_root_only_permissions=False,
        resolution_guidance="Keep candidate bundles free of credentials and secret material.",
    ),
    SecretDeliverySurface(
        surface="promotion_packet",
        title="Promotion packet",
        plan_section="3.7",
        embedded=True,
        baseline_supported=False,
        conditional_only=False,
        requires_root_only_permissions=False,
        resolution_guidance="Keep promotion packets free of credentials and secret material.",
    ),
    SecretDeliverySurface(
        surface="log",
        title="Log stream",
        plan_section="3.7",
        embedded=True,
        baseline_supported=False,
        conditional_only=False,
        requires_root_only_permissions=False,
        resolution_guidance="Strip credentials from logs and redact them before retention.",
    ),
    SecretDeliverySurface(
        surface="shell_history",
        title="Shell history",
        plan_section="3.7",
        embedded=True,
        baseline_supported=False,
        conditional_only=False,
        requires_root_only_permissions=False,
        resolution_guidance="Keep credentials out of shell history and operator transcripts.",
    ),
    SecretDeliverySurface(
        surface="systemd_unit_file",
        title="Systemd unit file",
        plan_section="3.7",
        embedded=True,
        baseline_supported=False,
        conditional_only=False,
        requires_root_only_permissions=False,
        resolution_guidance="Inject secrets from controlled paths or services, never unit files.",
    ),
)


_ZONE_INDEX: dict[str, TrustZone] = {zone.zone_id: zone for zone in TRUST_ZONES}
_DELIVERY_SURFACE_INDEX: dict[str, SecretDeliverySurface] = {
    surface.surface: surface for surface in SECRET_DELIVERY_SURFACES
}


def trust_zone_ids() -> list[str]:
    return [zone.zone_id for zone in TRUST_ZONES]


def secret_delivery_surface_keys() -> list[str]:
    return [surface.surface for surface in SECRET_DELIVERY_SURFACES]


def get_trust_zone(zone_id: str) -> TrustZone:
    return _ZONE_INDEX[zone_id]


def _normalize_items(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values}))


def _diagnostic(
    *,
    zone: str,
    status: str,
    reason_code: str | None,
    plan_section: str,
    boundary_crossed: str,
    surface: str,
    secret_type: str | None,
    expected_control: str,
    diagnostic_context: dict[str, Any],
    resolution_guidance: str,
    explanation: str,
) -> TrustZoneDiagnostic:
    return TrustZoneDiagnostic(
        zone=zone,
        status=status,
        reason_code=reason_code,
        plan_section=plan_section,
        boundary_crossed=boundary_crossed,
        surface=surface,
        secret_type=secret_type,
        expected_control=expected_control,
        diagnostic_context=diagnostic_context,
        resolution_guidance=resolution_guidance,
        explanation=explanation,
    )


def evaluate_zone_workloads(
    zone_id: str,
    observed_workloads: Iterable[str],
) -> TrustZoneDiagnostic:
    zone = get_trust_zone(zone_id)
    observed = _normalize_items(observed_workloads)
    misplaced = tuple(
        workload for workload in observed if workload not in zone.allowed_workloads
    )
    expected = ", ".join(zone.allowed_workloads)

    if misplaced:
        return _diagnostic(
            zone=zone.zone_id,
            status="violation",
            reason_code=f"TRUST_ZONE_WORKLOAD_MISPLACED_{zone.zone_id.upper()}",
            plan_section=zone.plan_section,
            boundary_crossed="trust_zone_workload",
            surface="host_workload",
            secret_type=None,
            expected_control=f"{zone.title} may only run workloads: {expected}.",
            diagnostic_context={
                "observed_workloads": list(observed),
                "misplaced_workloads": list(misplaced),
            },
            resolution_guidance=zone.resolution_guidance,
            explanation=(
                f"{zone.title} observed workloads outside its trust zone: "
                f"{', '.join(misplaced)}."
            ),
        )

    return _diagnostic(
        zone=zone.zone_id,
        status="pass",
        reason_code=None,
        plan_section=zone.plan_section,
        boundary_crossed="trust_zone_workload",
        surface="host_workload",
        secret_type=None,
        expected_control=f"{zone.title} may only run workloads: {expected}.",
        diagnostic_context={"observed_workloads": list(observed)},
        resolution_guidance=zone.resolution_guidance,
        explanation=f"{zone.title} workload placement stays inside the declared zone.",
    )


def evaluate_zone_secret_inventory(
    zone_id: str,
    observed_secret_types: Iterable[str],
) -> list[TrustZoneDiagnostic]:
    zone = get_trust_zone(zone_id)
    observed = _normalize_items(observed_secret_types)
    unauthorized = tuple(
        secret_type
        for secret_type in observed
        if secret_type not in zone.allowed_secret_types
    )
    expected = ", ".join(zone.allowed_secret_types)

    if not unauthorized:
        return [
            _diagnostic(
                zone=zone.zone_id,
                status="pass",
                reason_code=None,
                plan_section=zone.plan_section,
                boundary_crossed="credential_domain",
                surface="zone_secret_inventory",
                secret_type=None,
                expected_control=(
                    f"{zone.title} may only hold credentials from domains: {expected}."
                ),
                diagnostic_context={"observed_secret_types": list(observed)},
                resolution_guidance=zone.resolution_guidance,
                explanation=(
                    f"{zone.title} secret inventory stays within its allowed "
                    "credential domains."
                ),
            )
        ]

    return [
        _diagnostic(
            zone=zone.zone_id,
            status="violation",
            reason_code=f"TRUST_ZONE_SECRET_EXPOSURE_{zone.zone_id.upper()}",
            plan_section=zone.plan_section,
            boundary_crossed="credential_domain",
            surface="zone_secret_inventory",
            secret_type=secret_type,
            expected_control=(
                f"{zone.title} may only hold credentials from domains: {expected}."
            ),
            diagnostic_context={
                "observed_secret_types": list(observed),
                "unauthorized_secret_types": list(unauthorized),
            },
            resolution_guidance=zone.resolution_guidance,
            explanation=(
                f"{zone.title} holds {secret_type}, which crosses the declared "
                "credential boundary."
            ),
        )
        for secret_type in unauthorized
    ]


def evaluate_opsd_artifact_permissions(
    *,
    reads_approved_artifacts: bool,
    writes_evidence: bool,
    mutates_raw_archives: bool,
    mutates_releases: bool,
) -> TrustZoneDiagnostic:
    context = {
        "reads_approved_artifacts": reads_approved_artifacts,
        "writes_evidence": writes_evidence,
        "mutates_raw_archives": mutates_raw_archives,
        "mutates_releases": mutates_releases,
    }
    expected_control = (
        "opsd may read approved artifacts and write evidence, but may not "
        "mutate raw archives or release surfaces."
    )
    resolution = (
        "Limit opsd to approved artifact reads and evidence writes; keep raw "
        "archives and release surfaces immutable from operations."
    )
    allowed = (
        reads_approved_artifacts
        and writes_evidence
        and not mutates_raw_archives
        and not mutates_releases
    )

    if allowed:
        return _diagnostic(
            zone="operations",
            status="pass",
            reason_code=None,
            plan_section="3.4",
            boundary_crossed="artifact_mutation_boundary",
            surface="artifact_store",
            secret_type=None,
            expected_control=expected_control,
            diagnostic_context=context,
            resolution_guidance=resolution,
            explanation="opsd stays inside its artifact read/write boundary.",
        )

    return _diagnostic(
        zone="operations",
        status="violation",
        reason_code="TRUST_ZONE_OPSD_BOUNDARY_VIOLATION",
        plan_section="3.4",
        boundary_crossed="artifact_mutation_boundary",
        surface="artifact_store",
        secret_type=None,
        expected_control=expected_control,
        diagnostic_context=context,
        resolution_guidance=resolution,
        explanation="opsd exceeded its allowed artifact boundary or lacks required evidence access.",
    )


def evaluate_dashboard_access(role: str) -> TrustZoneDiagnostic:
    expected_control = "Dashboards must use read-only credentials."
    if role == "read_only":
        return _diagnostic(
            zone="dashboard",
            status="pass",
            reason_code=None,
            plan_section="3.4",
            boundary_crossed="least_privilege",
            surface="dashboard",
            secret_type="dashboard_credential",
            expected_control=expected_control,
            diagnostic_context={"role": role},
            resolution_guidance="Keep dashboards on read-only roles.",
            explanation="Dashboard access stays read-only.",
        )

    return _diagnostic(
        zone="dashboard",
        status="violation",
        reason_code="TRUST_ZONE_DASHBOARD_ROLE_NOT_READ_ONLY",
        plan_section="3.4",
        boundary_crossed="least_privilege",
        surface="dashboard",
        secret_type="dashboard_credential",
        expected_control=expected_control,
        diagnostic_context={"role": role},
        resolution_guidance="Demote dashboard access to a read-only credential.",
        explanation="Dashboard access is not read-only, so the least-privilege boundary is broken.",
    )


def evaluate_storage_access(
    *,
    credential_scope: str,
    least_privilege: bool,
    zone: str = "operations",
) -> TrustZoneDiagnostic:
    expected_control = "Object storage prefixes and buckets use least-privilege credentials."
    context = {
        "credential_scope": credential_scope,
        "least_privilege": least_privilege,
    }
    if least_privilege and credential_scope not in {"account_admin", "wildcard"}:
        return _diagnostic(
            zone=zone,
            status="pass",
            reason_code=None,
            plan_section="3.4",
            boundary_crossed="least_privilege",
            surface="object_storage",
            secret_type="storage_prefix_credential",
            expected_control=expected_control,
            diagnostic_context=context,
            resolution_guidance="Keep storage access scoped to the required prefixes and buckets only.",
            explanation="Storage credentials stay scoped to least-privilege access.",
        )

    return _diagnostic(
        zone=zone,
        status="violation",
        reason_code="TRUST_ZONE_STORAGE_NOT_LEAST_PRIVILEGE",
        plan_section="3.4",
        boundary_crossed="least_privilege",
        surface="object_storage",
        secret_type="storage_prefix_credential",
        expected_control=expected_control,
        diagnostic_context=context,
        resolution_guidance="Replace broad storage credentials with prefix- or bucket-scoped access.",
        explanation="Storage credentials are broader than the least-privilege boundary allows.",
    )


def evaluate_secret_delivery(
    *,
    secret_type: str,
    surface: str,
    zone: str = "operations",
    credential_domain_growth: bool = False,
    root_only_permissions: bool = True,
) -> TrustZoneDiagnostic:
    definition = _DELIVERY_SURFACE_INDEX.get(surface)
    if definition is None:
        return _diagnostic(
            zone=zone,
            status="violation",
            reason_code="TRUST_ZONE_SECRET_DELIVERY_UNKNOWN_SURFACE",
            plan_section="3.7",
            boundary_crossed="runtime_secret_delivery",
            surface=surface,
            secret_type=secret_type,
            expected_control="Secrets must use a declared delivery surface.",
            diagnostic_context={
                "credential_domain_growth": credential_domain_growth,
                "root_only_permissions": root_only_permissions,
            },
            resolution_guidance="Map the secret to a declared delivery surface before approving runtime use.",
            explanation=f"{secret_type} appeared on an undeclared delivery surface: {surface}.",
        )

    context = {
        "credential_domain_growth": credential_domain_growth,
        "root_only_permissions": root_only_permissions,
        "conditional_only": definition.conditional_only,
    }
    expected_control = (
        "Operational secrets are injected from controlled paths or services "
        "and never embedded in source, manifests, logs, or unit files."
    )

    if definition.embedded:
        return _diagnostic(
            zone=zone,
            status="violation",
            reason_code=f"TRUST_ZONE_SECRET_EMBEDDED_{definition.surface.upper()}",
            plan_section=definition.plan_section,
            boundary_crossed="runtime_secret_delivery",
            surface=definition.surface,
            secret_type=secret_type,
            expected_control=expected_control,
            diagnostic_context=context,
            resolution_guidance=definition.resolution_guidance,
            explanation=f"{secret_type} is embedded in {definition.title.lower()}.",
        )

    if definition.requires_root_only_permissions and not root_only_permissions:
        return _diagnostic(
            zone=zone,
            status="violation",
            reason_code="TRUST_ZONE_SECRET_FILE_NOT_ROOT_ONLY",
            plan_section=definition.plan_section,
            boundary_crossed="runtime_secret_delivery",
            surface=definition.surface,
            secret_type=secret_type,
            expected_control=expected_control,
            diagnostic_context=context,
            resolution_guidance=definition.resolution_guidance,
            explanation=(
                f"{secret_type} uses {definition.title.lower()} without the "
                "required root-only permissions."
            ),
        )

    if credential_domain_growth and definition.surface != "secret_service":
        return _diagnostic(
            zone=zone,
            status="violation",
            reason_code="TRUST_ZONE_SECRET_DELIVERY_INSUFFICIENT",
            plan_section=definition.plan_section,
            boundary_crossed="runtime_secret_delivery",
            surface=definition.surface,
            secret_type=secret_type,
            expected_control=(
                "Once credential domains grow, secret delivery must graduate to "
                "a heavier managed surface."
            ),
            diagnostic_context=context,
            resolution_guidance=(
                "Promote secret delivery to a managed secret service once the "
                "simple baseline is no longer sufficient."
            ),
            explanation=(
                f"{secret_type} still uses {definition.title.lower()} even "
                "though credential-domain growth requires a heavier solution."
            ),
        )

    explanation = f"{secret_type} uses {definition.title.lower()}."
    if definition.conditional_only:
        explanation += " This is acceptable and matches the conditional upgrade path."

    return _diagnostic(
        zone=zone,
        status="pass",
        reason_code=None,
        plan_section=definition.plan_section,
        boundary_crossed="runtime_secret_delivery",
        surface=definition.surface,
        secret_type=secret_type,
        expected_control=expected_control,
        diagnostic_context=context,
        resolution_guidance=definition.resolution_guidance,
        explanation=explanation,
    )


def evaluate_break_glass_access(
    *,
    accessed: bool,
    stored_separately: bool,
    mounted_into_standard_process: bool,
    incident_recorded: bool,
    rotated_after_use: bool,
    reviewed_before_next_live: bool,
) -> list[TrustZoneDiagnostic]:
    diagnostics: list[TrustZoneDiagnostic] = []
    storage_ok = stored_separately and not mounted_into_standard_process
    storage_context = {
        "accessed": accessed,
        "stored_separately": stored_separately,
        "mounted_into_standard_process": mounted_into_standard_process,
    }

    if storage_ok:
        diagnostics.append(
            _diagnostic(
                zone="operations",
                status="pass",
                reason_code=None,
                plan_section="3.7",
                boundary_crossed="break_glass_workflow",
                surface="break_glass_storage",
                secret_type="break_glass_credential",
                expected_control=(
                    "Break-glass credentials are stored separately and never "
                    "mounted into the standard trading process."
                ),
                diagnostic_context=storage_context,
                resolution_guidance=(
                    "Keep break-glass credentials separate from normal runtime "
                    "credentials."
                ),
                explanation=(
                    "Break-glass credentials are stored separately from the "
                    "standard runtime process."
                ),
            )
        )
    else:
        diagnostics.append(
            _diagnostic(
                zone="operations",
                status="violation",
                reason_code=(
                    "TRUST_ZONE_BREAK_GLASS_MOUNTED_IN_STANDARD_PROCESS"
                    if mounted_into_standard_process
                    else "TRUST_ZONE_BREAK_GLASS_STORAGE_NOT_SEPARATE"
                ),
                plan_section="3.7",
                boundary_crossed="break_glass_workflow",
                surface=(
                    "standard_trading_process"
                    if mounted_into_standard_process
                    else "break_glass_storage"
                ),
                secret_type="break_glass_credential",
                expected_control=(
                    "Break-glass credentials are stored separately and never "
                    "mounted into the standard trading process."
                ),
                diagnostic_context=storage_context,
                resolution_guidance=(
                    "Separate break-glass credentials from routine runtime "
                    "credentials and remove them from the standard process."
                ),
                explanation=(
                    "Break-glass credentials are not isolated from the normal "
                    "runtime path."
                ),
            )
        )

    if not accessed:
        return diagnostics

    checks = (
        (
            incident_recorded,
            "incident_record",
            "TRUST_ZONE_BREAK_GLASS_INCIDENT_MISSING",
            "Every break-glass access creates an incident record.",
            "Break-glass access recorded an incident.",
            "Break-glass access occurred without an incident record.",
        ),
        (
            rotated_after_use,
            "credential_rotation",
            "TRUST_ZONE_BREAK_GLASS_ROTATION_MISSING",
            "Every break-glass access requires post-use credential rotation.",
            "Break-glass access triggered post-use credential rotation.",
            "Break-glass access did not trigger credential rotation.",
        ),
        (
            reviewed_before_next_live,
            "next_live_review",
            "TRUST_ZONE_BREAK_GLASS_REVIEW_MISSING",
            "Every break-glass access is reviewed before the next live session.",
            "Break-glass access was reviewed before the next live session.",
            "Break-glass access was not reviewed before the next live session.",
        ),
    )

    for condition_met, surface, reason_code, expected_control, success, failure in checks:
        diagnostics.append(
            _diagnostic(
                zone="operations",
                status="pass" if condition_met else "violation",
                reason_code=None if condition_met else reason_code,
                plan_section="3.7",
                boundary_crossed="break_glass_workflow",
                surface=surface,
                secret_type="break_glass_credential",
                expected_control=expected_control,
                diagnostic_context={"accessed": accessed, "condition_met": condition_met},
                resolution_guidance=expected_control,
                explanation=success if condition_met else failure,
            )
        )

    return diagnostics


def evaluate_trust_zone_policy(
    *,
    zone_workloads: dict[str, Iterable[str]],
    zone_secret_inventory: dict[str, Iterable[str]],
    opsd_capabilities: dict[str, bool],
    dashboard_role: str,
    storage_access: dict[str, Any],
    secret_delivery_observations: list[dict[str, Any]],
    break_glass_state: dict[str, Any],
) -> dict[str, Any]:
    diagnostics: list[TrustZoneDiagnostic] = []

    for zone in TRUST_ZONES:
        diagnostics.append(
            evaluate_zone_workloads(zone.zone_id, zone_workloads.get(zone.zone_id, ()))
        )
        diagnostics.extend(
            evaluate_zone_secret_inventory(
                zone.zone_id, zone_secret_inventory.get(zone.zone_id, ())
            )
        )

    diagnostics.append(
        evaluate_opsd_artifact_permissions(
            reads_approved_artifacts=opsd_capabilities["reads_approved_artifacts"],
            writes_evidence=opsd_capabilities["writes_evidence"],
            mutates_raw_archives=opsd_capabilities["mutates_raw_archives"],
            mutates_releases=opsd_capabilities["mutates_releases"],
        )
    )
    diagnostics.append(evaluate_dashboard_access(dashboard_role))
    diagnostics.append(
        evaluate_storage_access(
            credential_scope=str(storage_access["credential_scope"]),
            least_privilege=bool(storage_access["least_privilege"]),
            zone=str(storage_access.get("zone", "operations")),
        )
    )

    for observation in secret_delivery_observations:
        diagnostics.append(
            evaluate_secret_delivery(
                secret_type=str(observation["secret_type"]),
                surface=str(observation["surface"]),
                zone=str(observation.get("zone", "operations")),
                credential_domain_growth=bool(
                    observation.get("credential_domain_growth", False)
                ),
                root_only_permissions=bool(
                    observation.get("root_only_permissions", True)
                ),
            )
        )

    diagnostics.extend(
        evaluate_break_glass_access(
            accessed=bool(break_glass_state["accessed"]),
            stored_separately=bool(break_glass_state["stored_separately"]),
            mounted_into_standard_process=bool(
                break_glass_state["mounted_into_standard_process"]
            ),
            incident_recorded=bool(break_glass_state["incident_recorded"]),
            rotated_after_use=bool(break_glass_state["rotated_after_use"]),
            reviewed_before_next_live=bool(
                break_glass_state["reviewed_before_next_live"]
            ),
        )
    )

    return {
        "allowed": all(diagnostic.status == "pass" for diagnostic in diagnostics),
        "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
    }
