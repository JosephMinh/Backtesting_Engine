/// Human-readable role summary for the crate.
pub const CRATE_ROLE: &str = "canonical signal kernels and deterministic shared compute";

/// Approved artifact roots that kernel code may load from.
pub const APPROVED_ARTIFACT_ROOTS: &[&str] = &[
    "candidate_bundles",
    "data_profile_releases",
    "resolved_context_bundles",
    "signal_kernels",
];

/// Classifies the allowed kernel artifact roots.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ArtifactClass {
    CandidateBundle,
    DataProfileRelease,
    ResolvedContextBundle,
    SignalKernel,
}

impl ArtifactClass {
    /// Returns the canonical relative root for the artifact class.
    pub const fn root(self) -> &'static str {
        match self {
            Self::CandidateBundle => "candidate_bundles",
            Self::DataProfileRelease => "data_profile_releases",
            Self::ResolvedContextBundle => "resolved_context_bundles",
            Self::SignalKernel => "signal_kernels",
        }
    }
}

/// Errors for invalid artifact references.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ArtifactBoundaryError {
    AbsolutePath,
    ParentTraversal,
    MissingLeaf,
    UnknownRoot(String),
}

/// A canonical reference to an approved kernel-facing artifact.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ApprovedArtifactRef {
    relative_path: String,
}

impl ApprovedArtifactRef {
    /// Validates and stores a relative artifact path rooted in an approved area.
    pub fn new(path: impl Into<String>) -> Result<Self, ArtifactBoundaryError> {
        let relative_path = path.into();
        if relative_path.starts_with('/') {
            return Err(ArtifactBoundaryError::AbsolutePath);
        }
        if relative_path.split('/').any(|segment| segment == "..") {
            return Err(ArtifactBoundaryError::ParentTraversal);
        }
        let mut segments = relative_path.split('/');
        let Some(root) = segments.next() else {
            return Err(ArtifactBoundaryError::MissingLeaf);
        };
        let has_leaf = segments.next().is_some();
        if !has_leaf {
            return Err(ArtifactBoundaryError::MissingLeaf);
        }
        if !APPROVED_ARTIFACT_ROOTS.contains(&root) {
            return Err(ArtifactBoundaryError::UnknownRoot(root.to_owned()));
        }
        Ok(Self { relative_path })
    }

    /// Returns the validated relative path.
    pub fn relative_path(&self) -> &str {
        &self.relative_path
    }

    /// Returns the validated artifact root.
    pub fn root(&self) -> &str {
        self.relative_path
            .split_once('/')
            .map_or(self.relative_path.as_str(), |(root, _)| root)
    }
}

/// Workspace-level contract for kernel artifact access.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct KernelBoundary {
    pub readable_artifact_roots: &'static [&'static str],
    pub writable_artifact_roots: &'static [&'static str],
}

/// Kernels only read approved artifacts and never mutate operational state.
pub const KERNEL_BOUNDARY: KernelBoundary = KernelBoundary {
    readable_artifact_roots: APPROVED_ARTIFACT_ROOTS,
    writable_artifact_roots: &[],
};

#[cfg(test)]
mod tests {
    use super::{
        APPROVED_ARTIFACT_ROOTS, ApprovedArtifactRef, ArtifactBoundaryError, ArtifactClass,
        KERNEL_BOUNDARY,
    };

    #[test]
    fn artifact_class_roots_are_explicit() {
        assert_eq!("candidate_bundles", ArtifactClass::CandidateBundle.root());
        assert_eq!(
            "data_profile_releases",
            ArtifactClass::DataProfileRelease.root()
        );
        assert_eq!(
            "resolved_context_bundles",
            ArtifactClass::ResolvedContextBundle.root()
        );
        assert_eq!("signal_kernels", ArtifactClass::SignalKernel.root());
    }

    #[test]
    fn artifact_refs_require_an_approved_root_and_leaf() {
        let artifact = ApprovedArtifactRef::new("candidate_bundles/gold_momentum.json")
            .expect("candidate bundle path should validate");
        assert_eq!("candidate_bundles", artifact.root());
        assert_eq!(
            "candidate_bundles/gold_momentum.json",
            artifact.relative_path()
        );
    }

    #[test]
    fn artifact_refs_reject_unsafe_paths() {
        assert_eq!(
            Err(ArtifactBoundaryError::AbsolutePath),
            ApprovedArtifactRef::new("/candidate_bundles/gold_momentum.json")
        );
        assert_eq!(
            Err(ArtifactBoundaryError::ParentTraversal),
            ApprovedArtifactRef::new("candidate_bundles/../secret.json")
        );
    }

    #[test]
    fn kernel_boundary_is_read_only() {
        assert_eq!(
            APPROVED_ARTIFACT_ROOTS,
            KERNEL_BOUNDARY.readable_artifact_roots
        );
        assert!(KERNEL_BOUNDARY.writable_artifact_roots.is_empty());
    }
}
