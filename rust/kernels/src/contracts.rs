use crate::{ApprovedArtifactRef, ArtifactBoundaryError, ArtifactClass};

const FNV_OFFSET_BASIS: u64 = 0xcbf29ce484222325;
const FNV_PRIME: u64 = 0x00000100000001b3;

/// Stable kernel identity metadata that lines up with the strategy-contract surface.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct KernelIdentity {
    pub strategy_family_id: &'static str,
    pub rust_crate: &'static str,
    pub python_binding_module: &'static str,
    pub kernel_abi_version: &'static str,
    pub state_serialization_version: &'static str,
    pub semantic_version: &'static str,
}

impl KernelIdentity {
    /// Returns a deterministic digest for the kernel identity contract.
    pub fn canonical_digest(self) -> String {
        let payload = format!(
            "{}|{}|{}|{}|{}|{}",
            self.strategy_family_id,
            self.rust_crate,
            self.python_binding_module,
            self.kernel_abi_version,
            self.state_serialization_version,
            self.semantic_version,
        );
        format!("{:016x}", fnv1a64(payload.as_bytes()))
    }
}

/// A market-data bar presented to a canonical signal kernel.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct BarInput {
    pub sequence_number: u64,
    pub close_ticks: i64,
}

/// High-level signal direction emitted by a kernel.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SignalDisposition {
    Long,
    Flat,
    Short,
}

impl SignalDisposition {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Long => "long",
            Self::Flat => "flat",
            Self::Short => "short",
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "long" => Some(Self::Long),
            "flat" => Some(Self::Flat),
            "short" => Some(Self::Short),
            _ => None,
        }
    }
}

/// One deterministic kernel decision emitted after warmup is satisfied.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SignalDecision {
    pub sequence_number: u64,
    pub signal_name: &'static str,
    pub score_ticks: i64,
    pub disposition: SignalDisposition,
}

/// The minimal executable interface every canonical signal kernel must satisfy.
pub trait SignalKernel {
    fn identity(&self) -> KernelIdentity;
    fn warmup_bars(&self) -> usize;
    fn evaluate_bar(&mut self, input: BarInput) -> Option<SignalDecision>;
}

/// Artifact-binding errors for kernel promotion/replay attachment surfaces.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum KernelBindingError {
    ArtifactBoundary(ArtifactBoundaryError),
    WrongRoot {
        field: &'static str,
        expected: &'static str,
        actual: String,
    },
}

impl From<ArtifactBoundaryError> for KernelBindingError {
    fn from(value: ArtifactBoundaryError) -> Self {
        Self::ArtifactBoundary(value)
    }
}

/// Explicit artifact bindings that attach a kernel identity to candidate/replay surfaces.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct KernelArtifactBinding {
    pub identity: KernelIdentity,
    pub candidate_bundle: ApprovedArtifactRef,
    pub resolved_context_bundle: ApprovedArtifactRef,
    pub signal_kernel: ApprovedArtifactRef,
}

impl KernelArtifactBinding {
    pub fn new(
        identity: KernelIdentity,
        candidate_bundle: impl Into<String>,
        resolved_context_bundle: impl Into<String>,
        signal_kernel: impl Into<String>,
    ) -> Result<Self, KernelBindingError> {
        let candidate_bundle = ApprovedArtifactRef::new(candidate_bundle)?;
        let resolved_context_bundle = ApprovedArtifactRef::new(resolved_context_bundle)?;
        let signal_kernel = ApprovedArtifactRef::new(signal_kernel)?;

        validate_root(
            "candidate_bundle",
            &candidate_bundle,
            ArtifactClass::CandidateBundle,
        )?;
        validate_root(
            "resolved_context_bundle",
            &resolved_context_bundle,
            ArtifactClass::ResolvedContextBundle,
        )?;
        validate_root("signal_kernel", &signal_kernel, ArtifactClass::SignalKernel)?;

        Ok(Self {
            identity,
            candidate_bundle,
            resolved_context_bundle,
            signal_kernel,
        })
    }
}

fn validate_root(
    field: &'static str,
    artifact: &ApprovedArtifactRef,
    expected_root: ArtifactClass,
) -> Result<(), KernelBindingError> {
    let expected = expected_root.root();
    let actual = artifact.root();
    if actual == expected {
        Ok(())
    } else {
        Err(KernelBindingError::WrongRoot {
            field,
            expected,
            actual: actual.to_owned(),
        })
    }
}

fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut hash = FNV_OFFSET_BASIS;
    for byte in bytes {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(FNV_PRIME);
    }
    hash
}

#[cfg(test)]
mod tests {
    use super::{KernelArtifactBinding, KernelBindingError, KernelIdentity, SignalDisposition};

    const TEST_IDENTITY: KernelIdentity = KernelIdentity {
        strategy_family_id: "gold_momentum",
        rust_crate: "rust/kernels",
        python_binding_module: "python.bindings._kernels.gold_momentum",
        kernel_abi_version: "abi_v2",
        state_serialization_version: "state_v2",
        semantic_version: "1.2.0",
    };

    #[test]
    fn canonical_digest_is_stable_for_identity_fields() {
        let digest = TEST_IDENTITY.canonical_digest();
        assert_eq!(digest, TEST_IDENTITY.canonical_digest());
        assert_eq!(16, digest.len());
    }

    #[test]
    fn signal_disposition_round_trips_through_strings() {
        for disposition in [
            SignalDisposition::Long,
            SignalDisposition::Flat,
            SignalDisposition::Short,
        ] {
            let parsed = SignalDisposition::parse(disposition.as_str())
                .expect("known disposition should parse");
            assert_eq!(disposition, parsed);
        }
        assert!(SignalDisposition::parse("sideways").is_none());
    }

    #[test]
    fn binding_requires_candidate_replay_and_kernel_roots() {
        let binding = KernelArtifactBinding::new(
            TEST_IDENTITY,
            "candidate_bundles/gold_momentum_bundle.json",
            "resolved_context_bundles/gold_momentum_context.json",
            "signal_kernels/gold_momentum.bin",
        )
        .expect("binding should validate");
        assert_eq!(TEST_IDENTITY, binding.identity);
        assert_eq!("candidate_bundles", binding.candidate_bundle.root());

        let err = KernelArtifactBinding::new(
            TEST_IDENTITY,
            "data_profile_releases/profile.toml",
            "resolved_context_bundles/gold_momentum_context.json",
            "signal_kernels/gold_momentum.bin",
        )
        .expect_err("candidate bundle root must be explicit");
        assert_eq!(
            KernelBindingError::WrongRoot {
                field: "candidate_bundle",
                expected: "candidate_bundles",
                actual: "data_profile_releases".to_owned(),
            },
            err
        );
    }
}
