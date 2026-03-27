//! Operational evidence archive, sealing, and query surfaces.
//!
//! This module intentionally stays isolated from the active `opsd` runtime
//! wiring so Tier E evidence archive behavior can be implemented and exercised
//! without colliding with adjacent in-flight lanes.

use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OperationalArtifactClass {
    Paper,
    ShadowLive,
    Replay,
    BrokerSession,
    Recovery,
    Parity,
    Drift,
    PostSessionReview,
}

impl OperationalArtifactClass {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Paper => "paper",
            Self::ShadowLive => "shadow_live",
            Self::Replay => "replay",
            Self::BrokerSession => "broker_session",
            Self::Recovery => "recovery",
            Self::Parity => "parity",
            Self::Drift => "drift",
            Self::PostSessionReview => "post_session_review",
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "paper" => Some(Self::Paper),
            "shadow_live" => Some(Self::ShadowLive),
            "replay" => Some(Self::Replay),
            "broker_session" => Some(Self::BrokerSession),
            "recovery" => Some(Self::Recovery),
            "parity" => Some(Self::Parity),
            "drift" => Some(Self::Drift),
            "post_session_review" => Some(Self::PostSessionReview),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EvidenceSealRequest {
    pub evidence_id: String,
    pub artifact_class: OperationalArtifactClass,
    pub candidate_id: String,
    pub deployment_instance_id: String,
    pub session_id: String,
    pub drill_id: Option<String>,
    pub retention_class: String,
    pub operator_summary: String,
    pub source_root: PathBuf,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ArchivedArtifact {
    pub relative_path: String,
    pub file_digest: String,
    pub size_bytes: u64,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ArchivedEvidenceManifest {
    pub manifest_id: String,
    pub entry_id: String,
    pub retained_artifact_id: String,
    pub evidence_id: String,
    pub artifact_class: String,
    pub candidate_id: String,
    pub deployment_instance_id: String,
    pub session_id: String,
    pub drill_id: Option<String>,
    pub retention_class: String,
    pub operator_summary: String,
    pub sealed_at_epoch_seconds: u64,
    pub contains_secrets: bool,
    pub redaction_policy: String,
    pub source_root: String,
    pub artifacts: Vec<ArchivedArtifact>,
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct EvidenceArchiveQuery {
    pub artifact_class: Option<String>,
    pub candidate_id: Option<String>,
    pub deployment_instance_id: Option<String>,
    pub session_id: Option<String>,
    pub drill_id: Option<String>,
}

fn fnv1a_hex(parts: &[String]) -> String {
    let mut hash: u64 = 0xcbf29ce484222325;
    for part in parts {
        for byte in part.as_bytes() {
            hash ^= u64::from(*byte);
            hash = hash.wrapping_mul(0x100000001b3);
        }
        hash ^= u64::from(b'|');
        hash = hash.wrapping_mul(0x100000001b3);
    }
    format!("{hash:016x}")
}

fn now_epoch_seconds() -> Result<u64, String> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .map_err(|err| format!("clock moved before unix epoch: {err}"))
}

fn collect_files(root: &Path, current: &Path, out: &mut Vec<PathBuf>) -> Result<(), String> {
    let entries = fs::read_dir(current).map_err(|err| {
        format!(
            "failed to read source directory {}: {err}",
            current.display()
        )
    })?;
    for entry in entries {
        let entry = entry.map_err(|err| {
            format!(
                "failed to read directory entry in {}: {err}",
                current.display()
            )
        })?;
        let path = entry.path();
        if path.is_dir() {
            collect_files(root, &path, out)?;
        } else if path.is_file() {
            let relative = path
                .strip_prefix(root)
                .map_err(|err| format!("failed to relativize {}: {err}", path.display()))?;
            out.push(relative.to_path_buf());
        }
    }
    Ok(())
}

fn render_manifest(manifest: &ArchivedEvidenceManifest) -> String {
    let mut lines = vec![
        format!("manifest_id={}", manifest.manifest_id),
        format!("entry_id={}", manifest.entry_id),
        format!("retained_artifact_id={}", manifest.retained_artifact_id),
        format!("evidence_id={}", manifest.evidence_id),
        format!("artifact_class={}", manifest.artifact_class),
        format!("candidate_id={}", manifest.candidate_id),
        format!("deployment_instance_id={}", manifest.deployment_instance_id),
        format!("session_id={}", manifest.session_id),
        format!("drill_id={}", manifest.drill_id.clone().unwrap_or_default()),
        format!("retention_class={}", manifest.retention_class),
        format!("operator_summary={}", manifest.operator_summary),
        format!(
            "sealed_at_epoch_seconds={}",
            manifest.sealed_at_epoch_seconds
        ),
        format!("contains_secrets={}", manifest.contains_secrets),
        format!("redaction_policy={}", manifest.redaction_policy),
        format!("source_root={}", manifest.source_root),
        format!("artifact_count={}", manifest.artifacts.len()),
    ];
    for (index, artifact) in manifest.artifacts.iter().enumerate() {
        lines.push(format!(
            "artifact[{index}].relative_path={}",
            artifact.relative_path
        ));
        lines.push(format!(
            "artifact[{index}].file_digest={}",
            artifact.file_digest
        ));
        lines.push(format!(
            "artifact[{index}].size_bytes={}",
            artifact.size_bytes
        ));
    }
    lines.join("\n")
}

fn parse_manifest(path: &Path) -> Result<ArchivedEvidenceManifest, String> {
    let raw = fs::read_to_string(path)
        .map_err(|err| format!("failed to read manifest {}: {err}", path.display()))?;
    let mut simple = std::collections::BTreeMap::new();
    let mut artifacts = Vec::new();
    let mut current_artifact = ArchivedArtifact {
        relative_path: String::new(),
        file_digest: String::new(),
        size_bytes: 0,
    };
    let mut current_index: Option<usize> = None;

    for line in raw.lines() {
        let Some((key, value)) = line.split_once('=') else {
            return Err(format!("invalid manifest line {line:?}"));
        };
        if let Some(index_key) = key.strip_prefix("artifact[") {
            let (index_text, field) = index_key
                .split_once("].")
                .ok_or_else(|| format!("invalid artifact key {key:?}"))?;
            if field.is_empty() {
                return Err(format!("invalid artifact key {key:?}"));
            }
            let index = index_text
                .parse::<usize>()
                .map_err(|err| format!("invalid artifact index {index_text:?}: {err}"))?;
            if current_index != Some(index) {
                if current_index.is_some() {
                    artifacts.push(current_artifact.clone());
                }
                current_artifact = ArchivedArtifact {
                    relative_path: String::new(),
                    file_digest: String::new(),
                    size_bytes: 0,
                };
                current_index = Some(index);
            }
            match field {
                "relative_path" => current_artifact.relative_path = value.to_string(),
                "file_digest" => current_artifact.file_digest = value.to_string(),
                "size_bytes" => {
                    current_artifact.size_bytes = value
                        .parse::<u64>()
                        .map_err(|err| format!("invalid size_bytes value {value:?}: {err}"))?
                }
                _ => return Err(format!("unknown artifact field {field:?}")),
            }
        } else {
            simple.insert(key.to_string(), value.to_string());
        }
    }
    if current_index.is_some() {
        artifacts.push(current_artifact);
    }
    let expected_artifact_count = simple
        .get("artifact_count")
        .ok_or_else(|| "artifact_count missing".to_string())?
        .parse::<usize>()
        .map_err(|err| format!("invalid artifact_count: {err}"))?;
    if artifacts.len() != expected_artifact_count {
        return Err(format!(
            "artifact_count mismatch: manifest declared {expected_artifact_count}, parsed {}",
            artifacts.len()
        ));
    }

    Ok(ArchivedEvidenceManifest {
        manifest_id: simple
            .get("manifest_id")
            .cloned()
            .ok_or_else(|| "manifest_id missing".to_string())?,
        entry_id: simple
            .get("entry_id")
            .cloned()
            .ok_or_else(|| "entry_id missing".to_string())?,
        retained_artifact_id: simple
            .get("retained_artifact_id")
            .cloned()
            .ok_or_else(|| "retained_artifact_id missing".to_string())?,
        evidence_id: simple
            .get("evidence_id")
            .cloned()
            .ok_or_else(|| "evidence_id missing".to_string())?,
        artifact_class: simple
            .get("artifact_class")
            .cloned()
            .ok_or_else(|| "artifact_class missing".to_string())?,
        candidate_id: simple
            .get("candidate_id")
            .cloned()
            .ok_or_else(|| "candidate_id missing".to_string())?,
        deployment_instance_id: simple
            .get("deployment_instance_id")
            .cloned()
            .ok_or_else(|| "deployment_instance_id missing".to_string())?,
        session_id: simple
            .get("session_id")
            .cloned()
            .ok_or_else(|| "session_id missing".to_string())?,
        drill_id: simple
            .get("drill_id")
            .cloned()
            .filter(|value| !value.is_empty()),
        retention_class: simple
            .get("retention_class")
            .cloned()
            .ok_or_else(|| "retention_class missing".to_string())?,
        operator_summary: simple
            .get("operator_summary")
            .cloned()
            .ok_or_else(|| "operator_summary missing".to_string())?,
        sealed_at_epoch_seconds: simple
            .get("sealed_at_epoch_seconds")
            .ok_or_else(|| "sealed_at_epoch_seconds missing".to_string())?
            .parse::<u64>()
            .map_err(|err| format!("invalid sealed_at_epoch_seconds: {err}"))?,
        contains_secrets: simple
            .get("contains_secrets")
            .ok_or_else(|| "contains_secrets missing".to_string())?
            .parse::<bool>()
            .map_err(|err| format!("invalid contains_secrets flag: {err}"))?,
        redaction_policy: simple
            .get("redaction_policy")
            .cloned()
            .ok_or_else(|| "redaction_policy missing".to_string())?,
        source_root: simple
            .get("source_root")
            .cloned()
            .ok_or_else(|| "source_root missing".to_string())?,
        artifacts,
    })
}

pub fn seal_evidence_bundle(
    request: &EvidenceSealRequest,
    archive_root: &Path,
) -> Result<ArchivedEvidenceManifest, String> {
    if request.evidence_id.trim().is_empty() {
        return Err("evidence_id must not be empty".to_string());
    }
    if request.candidate_id.trim().is_empty() {
        return Err("candidate_id must not be empty".to_string());
    }
    if request.deployment_instance_id.trim().is_empty() {
        return Err("deployment_instance_id must not be empty".to_string());
    }
    if request.session_id.trim().is_empty() {
        return Err("session_id must not be empty".to_string());
    }
    if request.retention_class.trim().is_empty() {
        return Err("retention_class must not be empty".to_string());
    }
    if !request.source_root.exists() {
        return Err(format!(
            "source_root does not exist: {}",
            request.source_root.display()
        ));
    }

    let mut relative_files = Vec::new();
    collect_files(
        &request.source_root,
        &request.source_root,
        &mut relative_files,
    )?;
    relative_files.sort();
    if relative_files.is_empty() {
        return Err(format!(
            "source_root has no files to archive: {}",
            request.source_root.display()
        ));
    }

    let sealed_at = now_epoch_seconds()?;
    let entry_suffix = fnv1a_hex(&[
        request.evidence_id.clone(),
        request.artifact_class.as_str().to_string(),
        request.candidate_id.clone(),
        request.deployment_instance_id.clone(),
        request.session_id.clone(),
        request.drill_id.clone().unwrap_or_default(),
        sealed_at.to_string(),
    ]);
    let entry_id = format!("opsd-evidence-entry-{entry_suffix}");
    let entry_root = archive_root.join("entries").join(&entry_id);
    let payload_root = entry_root.join("payload");
    fs::create_dir_all(&payload_root).map_err(|err| {
        format!(
            "failed to create payload root {}: {err}",
            payload_root.display()
        )
    })?;

    let mut artifacts = Vec::new();
    for relative_path in relative_files {
        let source_path = request.source_root.join(&relative_path);
        let destination_path = payload_root.join(&relative_path);
        if let Some(parent) = destination_path.parent() {
            fs::create_dir_all(parent).map_err(|err| {
                format!(
                    "failed to create destination parent {}: {err}",
                    parent.display()
                )
            })?;
        }
        fs::copy(&source_path, &destination_path).map_err(|err| {
            format!(
                "failed to copy {} to {}: {err}",
                source_path.display(),
                destination_path.display()
            )
        })?;
        let bytes = fs::read(&destination_path).map_err(|err| {
            format!(
                "failed to read copied artifact {}: {err}",
                destination_path.display()
            )
        })?;
        artifacts.push(ArchivedArtifact {
            relative_path: relative_path.display().to_string(),
            file_digest: fnv1a_hex(&[String::from_utf8_lossy(&bytes).to_string()]),
            size_bytes: bytes.len() as u64,
        });
    }

    let manifest = ArchivedEvidenceManifest {
        manifest_id: format!("opsd-evidence-manifest-{entry_suffix}"),
        entry_id: entry_id.clone(),
        retained_artifact_id: format!("tier_e_evidence/{}", request.evidence_id),
        evidence_id: request.evidence_id.clone(),
        artifact_class: request.artifact_class.as_str().to_string(),
        candidate_id: request.candidate_id.clone(),
        deployment_instance_id: request.deployment_instance_id.clone(),
        session_id: request.session_id.clone(),
        drill_id: request.drill_id.clone(),
        retention_class: request.retention_class.clone(),
        operator_summary: request.operator_summary.clone(),
        sealed_at_epoch_seconds: sealed_at,
        contains_secrets: false,
        redaction_policy: "structured_logs_redacted".to_string(),
        source_root: request.source_root.display().to_string(),
        artifacts,
    };

    fs::write(entry_root.join("manifest.txt"), render_manifest(&manifest)).map_err(|err| {
        format!(
            "failed to write manifest {}: {err}",
            entry_root.join("manifest.txt").display()
        )
    })?;
    Ok(manifest)
}

pub fn query_archive(
    archive_root: &Path,
    query: &EvidenceArchiveQuery,
) -> Result<Vec<ArchivedEvidenceManifest>, String> {
    let entries_root = archive_root.join("entries");
    if !entries_root.exists() {
        return Ok(Vec::new());
    }
    let mut manifests = Vec::new();
    let entries = fs::read_dir(&entries_root).map_err(|err| {
        format!(
            "failed to read archive entries {}: {err}",
            entries_root.display()
        )
    })?;
    for entry in entries {
        let entry = entry.map_err(|err| {
            format!(
                "failed to read archive entry in {}: {err}",
                entries_root.display()
            )
        })?;
        let manifest_path = entry.path().join("manifest.txt");
        if manifest_path.exists() {
            manifests.push(parse_manifest(&manifest_path)?);
        }
    }
    manifests.sort_by(|left, right| {
        left.evidence_id
            .cmp(&right.evidence_id)
            .then_with(|| left.entry_id.cmp(&right.entry_id))
    });

    Ok(manifests
        .into_iter()
        .filter(|manifest| {
            query
                .artifact_class
                .as_ref()
                .is_none_or(|value| manifest.artifact_class == *value)
                && query
                    .candidate_id
                    .as_ref()
                    .is_none_or(|value| manifest.candidate_id == *value)
                && query
                    .deployment_instance_id
                    .as_ref()
                    .is_none_or(|value| manifest.deployment_instance_id == *value)
                && query
                    .session_id
                    .as_ref()
                    .is_none_or(|value| manifest.session_id == *value)
                && query
                    .drill_id
                    .as_ref()
                    .is_none_or(|value| manifest.drill_id.as_deref() == Some(value.as_str()))
        })
        .collect())
}

#[cfg(test)]
mod tests {
    use super::{
        EvidenceArchiveQuery, EvidenceSealRequest, OperationalArtifactClass, query_archive,
        seal_evidence_bundle,
    };
    use std::env;
    use std::fs;
    use std::path::Path;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn unique_root(label: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("epoch should be monotonic in tests")
            .as_nanos();
        let temp_root = if Path::new("/dev/shm").exists() {
            PathBuf::from("/dev/shm")
        } else {
            env::temp_dir()
        };
        temp_root.join(format!("backtesting_engine_{label}_{nonce}"))
    }

    fn write_source_file(root: &PathBuf, relative_path: &str, content: &str) {
        let path = root.join(relative_path);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).expect("source parent must create");
        }
        fs::write(path, content).expect("source file must write");
    }

    #[test]
    fn sealing_copies_files_and_retains_manifest_metadata() {
        let source_root = unique_root("evidence_source");
        let archive_root = unique_root("evidence_archive");
        write_source_file(&source_root, "paper/runtime_log.txt", "paper-log");
        write_source_file(&source_root, "paper/manifest.txt", "paper-manifest");

        let manifest = seal_evidence_bundle(
            &EvidenceSealRequest {
                evidence_id: "paper_bundle_001".to_string(),
                artifact_class: OperationalArtifactClass::Paper,
                candidate_id: "candidate_gc_v1".to_string(),
                deployment_instance_id: "paper-gc-1".to_string(),
                session_id: "session-2026-03-18".to_string(),
                drill_id: Some("paper-route".to_string()),
                retention_class: "tier_e_archive".to_string(),
                operator_summary: "paper route archive".to_string(),
                source_root: source_root.clone(),
            },
            &archive_root,
        )
        .expect("sealing must succeed");

        assert_eq!("paper", manifest.artifact_class);
        assert_eq!("candidate_gc_v1", manifest.candidate_id);
        assert_eq!("tier_e_archive", manifest.retention_class);
        assert_eq!("structured_logs_redacted", manifest.redaction_policy);
        assert!(!manifest.contains_secrets);
        assert_eq!(2, manifest.artifacts.len());
        let copied_file = archive_root
            .join("entries")
            .join(&manifest.entry_id)
            .join("payload")
            .join("paper/runtime_log.txt");
        assert!(copied_file.exists());
        assert!(
            archive_root
                .join("entries")
                .join(&manifest.entry_id)
                .join("manifest.txt")
                .exists()
        );
        let queried = query_archive(&archive_root, &EvidenceArchiveQuery::default())
            .expect("round-trip query must succeed");
        assert_eq!(1, queried.len());
        assert_eq!(manifest, queried[0]);
    }

    #[test]
    fn query_filters_by_artifact_class_candidate_deployment_session_and_drill() {
        let archive_root = unique_root("evidence_query_archive");
        for (evidence_id, artifact_class, deployment_instance_id, drill_id) in [
            (
                "paper_bundle_001",
                OperationalArtifactClass::Paper,
                "deployment_gc_paper",
                Some("paper-route"),
            ),
            (
                "shadow_bundle_001",
                OperationalArtifactClass::ShadowLive,
                "deployment_gc_shadow",
                Some("shadow-live"),
            ),
            (
                "drift_bundle_001",
                OperationalArtifactClass::Drift,
                "deployment_gc_shadow",
                Some("drift-drill"),
            ),
        ] {
            let source_root = unique_root(evidence_id);
            write_source_file(&source_root, "artifact.txt", evidence_id);
            seal_evidence_bundle(
                &EvidenceSealRequest {
                    evidence_id: evidence_id.to_string(),
                    artifact_class,
                    candidate_id: "candidate_gc_v1".to_string(),
                    deployment_instance_id: deployment_instance_id.to_string(),
                    session_id: "session-2026-03-18".to_string(),
                    drill_id: drill_id.map(str::to_string),
                    retention_class: "tier_e_archive".to_string(),
                    operator_summary: format!("sealed {evidence_id}"),
                    source_root,
                },
                &archive_root,
            )
            .expect("sealing must succeed");
        }

        let drift_only = query_archive(
            &archive_root,
            &EvidenceArchiveQuery {
                artifact_class: Some("drift".to_string()),
                ..EvidenceArchiveQuery::default()
            },
        )
        .expect("query must succeed");
        assert_eq!(1, drift_only.len());
        assert_eq!("drift_bundle_001", drift_only[0].evidence_id);

        let session_match = query_archive(
            &archive_root,
            &EvidenceArchiveQuery {
                session_id: Some("session-2026-03-18".to_string()),
                candidate_id: Some("candidate_gc_v1".to_string()),
                ..EvidenceArchiveQuery::default()
            },
        )
        .expect("query must succeed");
        assert_eq!(3, session_match.len());

        let deployment_match = query_archive(
            &archive_root,
            &EvidenceArchiveQuery {
                deployment_instance_id: Some("deployment_gc_shadow".to_string()),
                ..EvidenceArchiveQuery::default()
            },
        )
        .expect("query must succeed");
        assert_eq!(2, deployment_match.len());
        let deployment_ids = deployment_match
            .iter()
            .map(|manifest| manifest.evidence_id.as_str())
            .collect::<Vec<_>>();
        assert_eq!(
            vec!["drift_bundle_001", "shadow_bundle_001"],
            deployment_ids
        );

        let drill_match = query_archive(
            &archive_root,
            &EvidenceArchiveQuery {
                drill_id: Some("shadow-live".to_string()),
                ..EvidenceArchiveQuery::default()
            },
        )
        .expect("query must succeed");
        assert_eq!(1, drill_match.len());
        assert_eq!("shadow_bundle_001", drill_match[0].evidence_id);
    }

    #[test]
    fn empty_source_root_is_rejected() {
        let source_root = unique_root("empty_source");
        let archive_root = unique_root("empty_archive");
        fs::create_dir_all(&source_root).expect("empty root must create");

        let error = seal_evidence_bundle(
            &EvidenceSealRequest {
                evidence_id: "empty_bundle".to_string(),
                artifact_class: OperationalArtifactClass::Replay,
                candidate_id: "candidate_gc_v1".to_string(),
                deployment_instance_id: "deployment_gc_replay".to_string(),
                session_id: "session-2026-03-18".to_string(),
                drill_id: Some("replay".to_string()),
                retention_class: "tier_e_archive".to_string(),
                operator_summary: "empty source".to_string(),
                source_root,
            },
            &archive_root,
        )
        .expect_err("empty source root must be rejected");

        assert!(error.contains("no files to archive"));
    }
}
