//! Canonical signal-kernel and artifact boundary contracts.
//!
//! This crate now owns three concrete responsibilities for the execution stack:
//! 1. artifact-boundary validation for kernel-facing inputs,
//! 2. explicit kernel identity/binding contracts that line up with the Python
//!    strategy-contract surface, and
//! 3. a deterministic canonical kernel implementation with crate-local replay
//!    fixtures and a smoke harness.

mod artifact;
mod contracts;
mod gold_momentum;
mod replay;

pub use artifact::{
    APPROVED_ARTIFACT_ROOTS, ApprovedArtifactRef, ArtifactBoundaryError, ArtifactClass, CRATE_ROLE,
    KERNEL_BOUNDARY, KernelBoundary,
};
pub use contracts::{
    BarInput, KernelArtifactBinding, KernelBindingError, KernelIdentity, SignalDecision,
    SignalDisposition, SignalKernel,
};
pub use gold_momentum::{
    GOLD_MOMENTUM_BINDING_MODULE, GOLD_MOMENTUM_IDENTITY, GOLD_MOMENTUM_SIGNAL_NAME,
    GoldMomentumKernel, GoldMomentumSnapshot, SnapshotDecodeError,
};
pub use replay::{
    FixtureDecision, FixtureLoadError, ReplayFixtureCase, SmokeDiff, SmokeLogRecord, SmokeReport,
    default_fixture_path, load_fixture_cases, render_smoke_report_json, run_fixture_case,
};
