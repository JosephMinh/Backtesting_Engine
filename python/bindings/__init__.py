from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BindingPackageContract:
    package_root: str
    rust_workspace_member: str
    future_extension_module: str
    role_summary: str


BINDING_PACKAGE_CONTRACT = BindingPackageContract(
    package_root="python/bindings",
    rust_workspace_member="rust/kernels",
    future_extension_module="python.bindings._kernels",
    role_summary="Python packaging surface for canonical Rust kernel bindings.",
)

from python.bindings._kernels import (  # noqa: E402
    BoundKernelIdentity,
    BoundKernelRun,
    KernelBindingError,
    run_gold_momentum,
)
from python.bindings.certification import (  # noqa: E402
    CertificationMismatch,
    EquivalenceCertificationReport,
    run_equivalence_certification,
)

__all__ = [
    "BINDING_PACKAGE_CONTRACT",
    "BindingPackageContract",
    "BoundKernelIdentity",
    "BoundKernelRun",
    "CertificationMismatch",
    "EquivalenceCertificationReport",
    "KernelBindingError",
    "run_equivalence_certification",
    "run_gold_momentum",
]
