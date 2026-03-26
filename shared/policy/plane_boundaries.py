"""Ownership lanes and import-boundary checks for the planned monorepo."""

from __future__ import annotations

import ast
import datetime
import importlib.util
import json
from dataclasses import asdict, dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


@unique
class PlaneId(Enum):
    PYTHON_RESEARCH = "python_research"
    PYTHON_BINDINGS = "python_bindings"
    RUST_KERNELS = "rust_kernels"
    RUST_OPERATIONS = "rust_operations"
    SHARED_CONTRACTS = "shared_contracts"


@dataclass(frozen=True)
class PlaneDefinition:
    plane_id: PlaneId
    title: str
    plan_section: str
    owned_path_prefixes: tuple[str, ...]
    owned_module_prefixes: tuple[str, ...]
    responsibilities: tuple[str, ...]
    allowed_dependencies: tuple[PlaneId, ...]


PLANE_DEFINITIONS: tuple[PlaneDefinition, ...] = (
    PlaneDefinition(
        plane_id=PlaneId.PYTHON_RESEARCH,
        title="Python research plane",
        plan_section="3.1",
        owned_path_prefixes=("python/research/",),
        owned_module_prefixes=("python.research",),
        responsibilities=(
            "ingestion",
            "release certification",
            "feature generation",
            "backtest orchestration",
            "tuning",
            "portability studies",
            "replay certification",
            "reporting",
        ),
        allowed_dependencies=(PlaneId.SHARED_CONTRACTS, PlaneId.PYTHON_BINDINGS),
    ),
    PlaneDefinition(
        plane_id=PlaneId.PYTHON_BINDINGS,
        title="Python bindings plane",
        plan_section="3.1",
        owned_path_prefixes=("python/bindings/",),
        owned_module_prefixes=("python.bindings",),
        responsibilities=(
            "Python bindings for canonical Rust kernels",
            "thin adaptation layer for promotable research",
        ),
        allowed_dependencies=(PlaneId.SHARED_CONTRACTS, PlaneId.RUST_KERNELS),
    ),
    PlaneDefinition(
        plane_id=PlaneId.RUST_KERNELS,
        title="Rust kernel plane",
        plan_section="3.1",
        owned_path_prefixes=("rust/kernels/",),
        owned_module_prefixes=(),
        responsibilities=(
            "canonical executable implementation of live-eligible signal kernels",
            "determinism-sensitive shared compute",
        ),
        allowed_dependencies=(PlaneId.SHARED_CONTRACTS,),
    ),
    PlaneDefinition(
        plane_id=PlaneId.RUST_OPERATIONS,
        title="Rust operational plane",
        plan_section="3.1",
        owned_path_prefixes=("rust/opsd/", "rust/guardian/", "rust/watchdog/"),
        owned_module_prefixes=(),
        responsibilities=(
            "paper, shadow-live, and live runtime",
            "deterministic state management",
            "broker integration",
            "risk enforcement",
            "recovery",
            "reconciliation",
            "session-readiness checks",
        ),
        allowed_dependencies=(PlaneId.SHARED_CONTRACTS, PlaneId.RUST_KERNELS),
    ),
    PlaneDefinition(
        plane_id=PlaneId.SHARED_CONTRACTS,
        title="Shared contracts",
        plan_section="3.1",
        owned_path_prefixes=("shared/", "sql/"),
        owned_module_prefixes=("shared",),
        responsibilities=(
            "schemas",
            "SQL migrations",
            "policy bundles",
            "compatibility matrices",
            "lifecycle state machines",
        ),
        allowed_dependencies=(),
    ),
)


@dataclass(frozen=True)
class ImportEdge:
    source_path: str
    source_line: int
    importer_module: str
    importer_plane: str
    imported_module: str
    imported_plane: str


@dataclass(frozen=True)
class BoundaryReport:
    source_path: str
    source_line: int
    importer_module: str
    importer_plane: str
    imported_module: str
    imported_plane: str
    boundary_crossed: str
    status: str
    reason_code: str
    expected_ownership_assignment: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass(frozen=True)
class SharedContractSurface:
    surface_id: str
    module: str
    source_path: str
    consumed_by: tuple[PlaneId, ...]
    plan_section: str
    purpose: str


@dataclass(frozen=True)
class ContractCompatibilityReport:
    surface_id: str
    module: str
    source_path: str
    owned_by: str
    consumer_planes: tuple[str, ...]
    compiled: bool
    reason_code: str
    explanation: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


SHARED_CONTRACT_SURFACES: tuple[SharedContractSurface, ...] = (
    SharedContractSurface(
        surface_id="scope_policy",
        module="shared.policy.scope",
        source_path="shared/policy/scope.py",
        consumed_by=(PlaneId.PYTHON_RESEARCH, PlaneId.RUST_OPERATIONS),
        plan_section="2.1-2.3",
        purpose="Scope classification and anti-scope rejection traces",
    ),
    SharedContractSurface(
        surface_id="guardrail_registry",
        module="shared.policy.principles",
        source_path="shared/policy/principles.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_KERNELS,
            PlaneId.RUST_OPERATIONS,
        ),
        plan_section="1.3",
        purpose="Canonical non-negotiable principle registry",
    ),
    SharedContractSurface(
        surface_id="guardrail_traces",
        module="shared.policy.guardrails",
        source_path="shared/policy/guardrails.py",
        consumed_by=(PlaneId.PYTHON_RESEARCH, PlaneId.RUST_OPERATIONS),
        plan_section="1.3",
        purpose="Structured decision traces for guardrail enforcement",
    ),
    SharedContractSurface(
        surface_id="live_lane_posture",
        module="shared.policy.posture",
        source_path="shared/policy/posture.py",
        consumed_by=(PlaneId.PYTHON_RESEARCH, PlaneId.RUST_OPERATIONS),
        plan_section="1.2",
        purpose="Approved live-lane posture contract",
    ),
    SharedContractSurface(
        surface_id="metadata_vs_telemetry_contract",
        module="shared.policy.metadata_telemetry",
        source_path="shared/policy/metadata_telemetry.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_KERNELS,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="3.3",
        purpose="Canonical metadata versus dense telemetry classification and derivability rules",
    ),
    SharedContractSurface(
        surface_id="clock_discipline_contract",
        module="shared.policy.clock_discipline",
        source_path="shared/policy/clock_discipline.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="3.5",
        purpose="UTC persistence, compiled session clocks, and skew-threshold enforcement rules",
    ),
    SharedContractSurface(
        surface_id="product_and_account_profiles",
        module="shared.policy.product_profiles",
        source_path="shared/policy/product_profiles.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="4.1",
        purpose="Canonical product behavior, account posture, and binding validation rules",
    ),
    SharedContractSurface(
        surface_id="storage_tiers_and_point_in_time_binding",
        module="shared.policy.storage_tiers",
        source_path="shared/policy/storage_tiers.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="5.1-5.2",
        purpose="Canonical storage-tier placement and promotable experiment binding rules",
    ),
    SharedContractSurface(
        surface_id="validation_and_release_lifecycle",
        module="shared.policy.release_validation",
        source_path="shared/policy/release_validation.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="5.3-5.4",
        purpose=(
            "Validation failure classification, sidecar-mask discipline, and release "
            "lifecycle state semantics"
        ),
    ),
    SharedContractSurface(
        surface_id="foundation_phase0_harness",
        module="shared.policy.foundation_harness",
        source_path="shared/policy/foundation_harness.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="11.2",
        purpose=(
            "Reproducible phase-0 foundation harness with setup, schema, compatibility, "
            "probe, property, and round-trip smoke evidence"
        ),
    ),
    SharedContractSurface(
        surface_id="databento_ibkr_bar_parity",
        module="shared.policy.bar_parity",
        source_path="shared/policy/bar_parity.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="6.8",
        purpose=(
            "Deterministic Databento-to-IBKR bar-parity certification across session, "
            "OHLCV, anchor, event-window, and availability semantics"
        ),
    ),
    SharedContractSurface(
        surface_id="execution_symbol_portability_and_native_validation",
        module="shared.policy.viability_gate",
        source_path="shared/policy/viability_gate.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="6.6-6.7",
        purpose=(
            "Formal portability certification and mandatory native 1OZ validation before "
            "finalist promotion"
        ),
    ),
    SharedContractSurface(
        surface_id="fast_screening_governance",
        module="shared.policy.fast_screening",
        source_path="shared/policy/fast_screening.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="6.9",
        purpose=(
            "Optional fast-screening eligibility, Nautilus equivalence retention, and "
            "non-promotable survivor-routing controls"
        ),
    ),
    SharedContractSurface(
        surface_id="strategy_contracts_and_canonical_signal_kernel",
        module="shared.policy.strategy_contract",
        source_path="shared/policy/strategy_contract.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.PYTHON_BINDINGS,
            PlaneId.RUST_KERNELS,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="7.1-7.2",
        purpose=(
            "Stable strategy-family contracts, one canonical promotable signal-kernel "
            "rule, and pre-freeze equivalence-certification requirements"
        ),
    ),
    SharedContractSurface(
        surface_id="baseline_risk_controls_and_waiver_defaults",
        module="shared.policy.baseline_risk_controls",
        source_path="shared/policy/baseline_risk_controls.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="5.2",
        purpose=(
            "Inherited live-lane position, loss, drawdown, delivery-fence, warm-up, "
            "margin, and overnight controls with signed-waiver traces"
        ),
    ),
    SharedContractSurface(
        surface_id="fully_loaded_economics",
        module="shared.policy.fully_loaded_economics",
        source_path="shared/policy/fully_loaded_economics.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="7.7",
        purpose=(
            "Gross, net-direct, and net-fully-loaded economics with explicit recurring "
            "cost allocation and execution-profile conditioning"
        ),
    ),
    SharedContractSurface(
        surface_id="solo_governance_workflows",
        module="shared.policy.solo_governance",
        source_path="shared/policy/solo_governance.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="11.3-11.4",
        purpose=(
            "Time-separated self-attestation, explicit waiver expiry, and incident "
            "corrective-action workflow contracts"
        ),
    ),
    SharedContractSurface(
        surface_id="verification_contract",
        module="shared.policy.verification_contract",
        source_path="shared/policy/verification_contract.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_KERNELS,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="11",
        purpose="Named verification surfaces and retained-artifact requirements",
    ),
    SharedContractSurface(
        surface_id="plane_boundaries",
        module="shared.policy.plane_boundaries",
        source_path="shared/policy/plane_boundaries.py",
        consumed_by=(
            PlaneId.PYTHON_RESEARCH,
            PlaneId.RUST_KERNELS,
            PlaneId.RUST_OPERATIONS,
            PlaneId.SHARED_CONTRACTS,
        ),
        plan_section="3.1",
        purpose="Ownership map and executable plane-boundary checks",
    ),
)


def get_plane_definition(plane_id: PlaneId) -> PlaneDefinition:
    for definition in PLANE_DEFINITIONS:
        if definition.plane_id == plane_id:
            return definition
    raise KeyError(f"Unknown plane id: {plane_id}")


def plane_for_module(module_name: str) -> PlaneId | None:
    for definition in PLANE_DEFINITIONS:
        for prefix in definition.owned_module_prefixes:
            if module_name == prefix or module_name.startswith(f"{prefix}."):
                return definition.plane_id
    return None


def plane_for_path(relative_path: str) -> PlaneId | None:
    normalized = relative_path.replace("\\", "/")
    for definition in PLANE_DEFINITIONS:
        for prefix in definition.owned_path_prefixes:
            if normalized.startswith(prefix):
                return definition.plane_id
    return None


def module_name_from_path(path: Path) -> tuple[str | None, bool]:
    if path.suffix != ".py":
        return None, False

    parts = list(path.with_suffix("").parts)
    if not parts:
        return None, False

    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]

    if not parts:
        return None, is_package

    return ".".join(parts), is_package


def _resolve_imported_module(
    importer_module: str, importer_is_package: bool, node: ast.ImportFrom
) -> str | None:
    if node.level == 0:
        return node.module

    current_package = (
        importer_module
        if importer_is_package
        else importer_module.rsplit(".", 1)[0]
    )
    relative_name = "." * node.level + (node.module or "")

    try:
        return importlib.util.resolve_name(relative_name, current_package)
    except ImportError:
        return None


def scan_internal_import_edges(root: Path | None = None) -> list[ImportEdge]:
    project_root = root or REPO_ROOT
    edges: list[ImportEdge] = []

    for directory in ("python", "shared"):
        base_dir = project_root / directory
        if not base_dir.exists():
            continue

        for file_path in sorted(base_dir.rglob("*.py")):
            relative_path = file_path.relative_to(project_root)
            importer_module, importer_is_package = module_name_from_path(relative_path)
            if importer_module is None:
                continue

            importer_plane = plane_for_module(importer_module)
            if importer_plane is None:
                continue

            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_plane = plane_for_module(alias.name)
                        if imported_plane is None:
                            continue
                        edges.append(
                            ImportEdge(
                                source_path=relative_path.as_posix(),
                                source_line=node.lineno,
                                importer_module=importer_module,
                                importer_plane=importer_plane.value,
                                imported_module=alias.name,
                                imported_plane=imported_plane.value,
                            )
                        )

                if isinstance(node, ast.ImportFrom):
                    imported_module = _resolve_imported_module(
                        importer_module, importer_is_package, node
                    )
                    if imported_module is None:
                        continue
                    imported_plane = plane_for_module(imported_module)
                    if imported_plane is None:
                        continue
                    edges.append(
                        ImportEdge(
                            source_path=relative_path.as_posix(),
                            source_line=node.lineno,
                            importer_module=importer_module,
                            importer_plane=importer_plane.value,
                            imported_module=imported_module,
                            imported_plane=imported_plane.value,
                        )
                    )

    return edges


def _expected_ownership_assignment(imported_plane: PlaneId) -> str:
    definition = get_plane_definition(imported_plane)
    owned_paths = ", ".join(definition.owned_path_prefixes)
    return (
        f"{definition.title} owns this dependency surface; keep the implementation under "
        f"{owned_paths} and consume it only through an allowed plane boundary."
    )


def evaluate_import_edge(edge: ImportEdge) -> BoundaryReport:
    importer_plane = PlaneId(edge.importer_plane)
    imported_plane = PlaneId(edge.imported_plane)
    importer_definition = get_plane_definition(importer_plane)

    allowed = imported_plane == importer_plane or imported_plane in importer_definition.allowed_dependencies
    boundary_crossed = f"{edge.importer_plane}->{edge.imported_plane}"

    if allowed:
        return BoundaryReport(
            source_path=edge.source_path,
            source_line=edge.source_line,
            importer_module=edge.importer_module,
            importer_plane=edge.importer_plane,
            imported_module=edge.imported_module,
            imported_plane=edge.imported_plane,
            boundary_crossed=boundary_crossed,
            status="pass",
            reason_code=f"ARCH_BOUNDARY_ALLOWED_{edge.importer_plane.upper()}_TO_{edge.imported_plane.upper()}",
            expected_ownership_assignment=_expected_ownership_assignment(imported_plane),
            explanation=(
                f"{importer_definition.title} is allowed to depend on "
                f"{get_plane_definition(imported_plane).title}."
            ),
        )

    return BoundaryReport(
        source_path=edge.source_path,
        source_line=edge.source_line,
        importer_module=edge.importer_module,
        importer_plane=edge.importer_plane,
        imported_module=edge.imported_module,
        imported_plane=edge.imported_plane,
        boundary_crossed=boundary_crossed,
        status="violation",
        reason_code=f"ARCH_BOUNDARY_VIOLATION_{edge.importer_plane.upper()}_TO_{edge.imported_plane.upper()}",
        expected_ownership_assignment=_expected_ownership_assignment(imported_plane),
        explanation=(
            f"{importer_definition.title} cannot import {get_plane_definition(imported_plane).title}; "
            "move shared interfaces into shared contracts or route the dependency through an allowed plane."
        ),
    )


def validate_import_boundaries(root: Path | None = None) -> list[BoundaryReport]:
    return [evaluate_import_edge(edge) for edge in scan_internal_import_edges(root)]


def shared_contract_compile_reports(root: Path | None = None) -> list[ContractCompatibilityReport]:
    project_root = root or REPO_ROOT
    reports: list[ContractCompatibilityReport] = []

    for surface in SHARED_CONTRACT_SURFACES:
        source_file = project_root / surface.source_path
        source_text = source_file.read_text(encoding="utf-8")
        compile(source_text, str(source_file), "exec")
        reports.append(
            ContractCompatibilityReport(
                surface_id=surface.surface_id,
                module=surface.module,
                source_path=surface.source_path,
                owned_by=PlaneId.SHARED_CONTRACTS.value,
                consumer_planes=tuple(plane.value for plane in surface.consumed_by),
                compiled=True,
                reason_code=f"ARCH_CONTRACT_COMPATIBLE_{surface.surface_id.upper()}",
                explanation=(
                    "Shared contract surface parses successfully and declares its intended "
                    "consumer planes."
                ),
            )
        )

    return reports
