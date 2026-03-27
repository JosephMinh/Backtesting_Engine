//! Session-readiness packet assembly and precondition-provider integration.
//!
//! This module stays intentionally isolated from the active `opsd` runtime and
//! reconciliation wiring so readiness truth can be modeled and exercised
//! without colliding with adjacent lanes.

use std::collections::BTreeSet;
use std::fs;
use std::path::Path;

/// Provider classes that may contribute to a session-readiness packet.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
pub enum ReadinessProviderKind {
    SessionEligibility,
    RuntimeRisk,
    BrokerState,
    ContractConformance,
    AuthoritativeReconciliation,
    ActivationLaneHealth,
    FeeSnapshot,
    MarginSnapshot,
    Entitlement,
    BackupFreshness,
    RestoreDrill,
    ClockHealth,
    SecretHealth,
    LedgerClose,
}

impl ReadinessProviderKind {
    /// Stable identifier for packet artifacts and logs.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::SessionEligibility => "session_eligibility",
            Self::RuntimeRisk => "runtime_risk",
            Self::BrokerState => "broker_state",
            Self::ContractConformance => "contract_conformance",
            Self::AuthoritativeReconciliation => "authoritative_reconciliation",
            Self::ActivationLaneHealth => "activation_lane_health",
            Self::FeeSnapshot => "fee_snapshot",
            Self::MarginSnapshot => "margin_snapshot",
            Self::Entitlement => "entitlement",
            Self::BackupFreshness => "backup_freshness",
            Self::RestoreDrill => "restore_drill",
            Self::ClockHealth => "clock_health",
            Self::SecretHealth => "secret_health",
            Self::LedgerClose => "ledger_close",
        }
    }
}

/// Provider-local state carried into readiness packet assembly.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProviderStatus {
    Pass,
    Blocked,
    ReviewRequired,
    Stale,
}

impl ProviderStatus {
    /// Stable identifier for packet artifacts and logs.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Pass => "pass",
            Self::Blocked => "blocked",
            Self::ReviewRequired => "review_required",
            Self::Stale => "stale",
        }
    }
}

/// Packet-level session-readiness state.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SessionReadinessStatus {
    Green,
    Blocked,
    Suspect,
    Invalid,
}

impl SessionReadinessStatus {
    /// Stable identifier for packet artifacts and logs.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Green => "green",
            Self::Blocked => "blocked",
            Self::Suspect => "suspect",
            Self::Invalid => "invalid",
        }
    }
}

/// One composable provider output consumed by packet assembly.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReadinessProviderOutput {
    pub provider_id: String,
    pub provider_kind: ReadinessProviderKind,
    pub status: ProviderStatus,
    pub reason_code: String,
    pub summary: String,
    pub source_artifact_id: String,
    pub component_digest: String,
    pub required_for_green: bool,
}

/// History entry retained for prior readiness packet outcomes.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReadinessHistoryEntry {
    pub packet_id: String,
    pub packet_digest: String,
    pub status: SessionReadinessStatus,
    pub reason_code: String,
    pub created_at_utc: String,
}

/// Request used to assemble one session-readiness packet.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SessionReadinessPacketRequest {
    pub packet_id: String,
    pub deployment_instance_id: String,
    pub session_id: String,
    pub valid_from_utc: String,
    pub valid_to_utc: String,
    pub source_promotion_packet_id: String,
    pub required_provider_kinds: Vec<ReadinessProviderKind>,
    pub providers: Vec<ReadinessProviderOutput>,
    pub previous_history: Vec<ReadinessHistoryEntry>,
    pub correlation_id: String,
    pub operator_summary: String,
}

/// Assembled readiness packet retained by the runtime.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SessionReadinessPacket {
    pub packet_id: String,
    pub packet_digest: String,
    pub deployment_instance_id: String,
    pub session_id: String,
    pub valid_from_utc: String,
    pub valid_to_utc: String,
    pub source_promotion_packet_id: String,
    pub status: SessionReadinessStatus,
    pub reason_code: String,
    pub retained_artifact_id: String,
    pub required_provider_kinds: Vec<String>,
    pub missing_required_provider_kinds: Vec<String>,
    pub blocked_provider_ids: Vec<String>,
    pub suspect_provider_ids: Vec<String>,
    pub providers: Vec<ReadinessProviderOutput>,
    pub history: Vec<ReadinessHistoryEntry>,
    pub summary: String,
}

fn fnv1a_hex(labels: &[String]) -> String {
    let mut hash: u64 = 0xcbf29ce484222325;
    for label in labels {
        for byte in label.as_bytes() {
            hash ^= u64::from(*byte);
            hash = hash.wrapping_mul(0x100000001b3);
        }
        hash ^= u64::from(b'|');
        hash = hash.wrapping_mul(0x100000001b3);
    }
    format!("{hash:016x}")
}

fn render_provider(provider: &ReadinessProviderOutput) -> String {
    [
        format!("provider_id={}", provider.provider_id),
        format!("provider_kind={}", provider.provider_kind.as_str()),
        format!("status={}", provider.status.as_str()),
        format!("reason_code={}", provider.reason_code),
        format!("summary={}", provider.summary),
        format!("source_artifact_id={}", provider.source_artifact_id),
        format!("component_digest={}", provider.component_digest),
        format!("required_for_green={}", provider.required_for_green),
    ]
    .join("\n")
}

fn render_request(request: &SessionReadinessPacketRequest) -> String {
    let mut lines = vec![
        format!("packet_id={}", request.packet_id),
        format!("deployment_instance_id={}", request.deployment_instance_id),
        format!("session_id={}", request.session_id),
        format!("valid_from_utc={}", request.valid_from_utc),
        format!("valid_to_utc={}", request.valid_to_utc),
        format!(
            "source_promotion_packet_id={}",
            request.source_promotion_packet_id
        ),
        format!("correlation_id={}", request.correlation_id),
        format!("operator_summary={}", request.operator_summary),
        format!(
            "required_provider_kinds={}",
            request
                .required_provider_kinds
                .iter()
                .map(|kind| kind.as_str())
                .collect::<Vec<_>>()
                .join(",")
        ),
    ];
    for (index, provider) in request.providers.iter().enumerate() {
        lines.push(format!("provider[{index}].{}", render_provider(provider)));
    }
    for (index, history) in request.previous_history.iter().enumerate() {
        lines.push(format!("history[{index}].packet_id={}", history.packet_id));
        lines.push(format!("history[{index}].digest={}", history.packet_digest));
        lines.push(format!(
            "history[{index}].status={}",
            history.status.as_str()
        ));
        lines.push(format!(
            "history[{index}].reason_code={}",
            history.reason_code
        ));
    }
    lines.join("\n")
}

fn render_packet(packet: &SessionReadinessPacket) -> String {
    let mut lines = vec![
        format!("packet_id={}", packet.packet_id),
        format!("packet_digest={}", packet.packet_digest),
        format!("deployment_instance_id={}", packet.deployment_instance_id),
        format!("session_id={}", packet.session_id),
        format!("valid_from_utc={}", packet.valid_from_utc),
        format!("valid_to_utc={}", packet.valid_to_utc),
        format!(
            "source_promotion_packet_id={}",
            packet.source_promotion_packet_id
        ),
        format!("status={}", packet.status.as_str()),
        format!("reason_code={}", packet.reason_code),
        format!("retained_artifact_id={}", packet.retained_artifact_id),
        format!(
            "required_provider_kinds={}",
            packet.required_provider_kinds.join(",")
        ),
        format!(
            "missing_required_provider_kinds={}",
            packet.missing_required_provider_kinds.join(",")
        ),
        format!(
            "blocked_provider_ids={}",
            packet.blocked_provider_ids.join(",")
        ),
        format!(
            "suspect_provider_ids={}",
            packet.suspect_provider_ids.join(",")
        ),
        format!("summary={}", packet.summary),
    ];
    for (index, provider) in packet.providers.iter().enumerate() {
        lines.push(format!("provider[{index}].{}", render_provider(provider)));
    }
    for (index, history) in packet.history.iter().enumerate() {
        lines.push(format!("history[{index}].packet_id={}", history.packet_id));
        lines.push(format!("history[{index}].digest={}", history.packet_digest));
        lines.push(format!(
            "history[{index}].status={}",
            history.status.as_str()
        ));
        lines.push(format!(
            "history[{index}].reason_code={}",
            history.reason_code
        ));
    }
    lines.join("\n")
}

fn invalid_packet(
    request: &SessionReadinessPacketRequest,
    issues: Vec<String>,
    reason_code: &str,
) -> SessionReadinessPacket {
    let reason_code = reason_code.to_string();
    let packet_digest = fnv1a_hex(&[
        request.packet_id.clone(),
        request.session_id.clone(),
        reason_code.clone(),
    ]);
    let mut history = request.previous_history.clone();
    history.push(ReadinessHistoryEntry {
        packet_id: request.packet_id.clone(),
        packet_digest: packet_digest.clone(),
        status: SessionReadinessStatus::Invalid,
        reason_code: reason_code.clone(),
        created_at_utc: request.valid_from_utc.clone(),
    });
    SessionReadinessPacket {
        packet_id: request.packet_id.clone(),
        packet_digest,
        deployment_instance_id: request.deployment_instance_id.clone(),
        session_id: request.session_id.clone(),
        valid_from_utc: request.valid_from_utc.clone(),
        valid_to_utc: request.valid_to_utc.clone(),
        source_promotion_packet_id: request.source_promotion_packet_id.clone(),
        status: SessionReadinessStatus::Invalid,
        reason_code,
        retained_artifact_id: format!("readiness_packets/{}.txt", request.packet_id),
        required_provider_kinds: request
            .required_provider_kinds
            .iter()
            .map(|kind| kind.as_str().to_string())
            .collect(),
        missing_required_provider_kinds: issues,
        blocked_provider_ids: Vec::new(),
        suspect_provider_ids: Vec::new(),
        providers: request.providers.clone(),
        history,
        summary: "The session-readiness packet request was invalid because one or more required providers or identifiers were missing.".to_string(),
    }
}

fn packet_digest(
    request: &SessionReadinessPacketRequest,
    status: SessionReadinessStatus,
    reason_code: &str,
    blocked_provider_ids: &[String],
    suspect_provider_ids: &[String],
    missing_required_provider_kinds: &[String],
) -> String {
    let mut labels = vec![
        request.packet_id.clone(),
        request.deployment_instance_id.clone(),
        request.session_id.clone(),
        request.valid_from_utc.clone(),
        request.valid_to_utc.clone(),
        request.source_promotion_packet_id.clone(),
        status.as_str().to_string(),
        reason_code.to_string(),
    ];
    labels.extend(
        request
            .required_provider_kinds
            .iter()
            .map(|kind| kind.as_str().to_string()),
    );
    labels.extend(blocked_provider_ids.iter().cloned());
    labels.extend(suspect_provider_ids.iter().cloned());
    labels.extend(missing_required_provider_kinds.iter().cloned());
    labels.extend(request.providers.iter().map(|provider| {
        format!(
            "{}:{}:{}:{}",
            provider.provider_id,
            provider.provider_kind.as_str(),
            provider.status.as_str(),
            provider.component_digest
        )
    }));
    fnv1a_hex(&labels)
}

/// Assembles one explicit session-readiness packet from composable provider outputs.
pub fn assemble_session_readiness_packet(
    request: &SessionReadinessPacketRequest,
) -> SessionReadinessPacket {
    let mut issues = Vec::new();
    if request.packet_id.trim().is_empty() {
        issues.push("packet_id".to_string());
    }
    if request.deployment_instance_id.trim().is_empty() {
        issues.push("deployment_instance_id".to_string());
    }
    if request.session_id.trim().is_empty() {
        issues.push("session_id".to_string());
    }
    if request.valid_from_utc.trim().is_empty() {
        issues.push("valid_from_utc".to_string());
    }
    if request.valid_to_utc.trim().is_empty() {
        issues.push("valid_to_utc".to_string());
    }
    if request.source_promotion_packet_id.trim().is_empty() {
        issues.push("source_promotion_packet_id".to_string());
    }
    if request.required_provider_kinds.is_empty() {
        issues.push("required_provider_kinds".to_string());
    }
    if request.providers.is_empty() {
        issues.push("providers".to_string());
    }
    if !issues.is_empty() {
        return invalid_packet(request, issues, "READINESS_PACKET_INVALID");
    }

    let available_kinds = request
        .providers
        .iter()
        .map(|provider| provider.provider_kind)
        .collect::<BTreeSet<_>>();
    let missing_required_provider_kinds = request
        .required_provider_kinds
        .iter()
        .filter(|kind| !available_kinds.contains(kind))
        .map(|kind| kind.as_str().to_string())
        .collect::<Vec<_>>();
    if !missing_required_provider_kinds.is_empty() {
        return invalid_packet(
            request,
            missing_required_provider_kinds,
            "READINESS_REQUIRED_PROVIDER_MISSING",
        );
    }

    let blocked_provider_ids = request
        .providers
        .iter()
        .filter(|provider| {
            provider.required_for_green
                && matches!(
                    provider.status,
                    ProviderStatus::Blocked | ProviderStatus::Stale
                )
        })
        .map(|provider| provider.provider_id.clone())
        .collect::<Vec<_>>();
    let suspect_provider_ids = request
        .providers
        .iter()
        .filter(|provider| {
            provider.required_for_green && provider.status == ProviderStatus::ReviewRequired
        })
        .map(|provider| provider.provider_id.clone())
        .collect::<Vec<_>>();

    let has_stale_provider = request
        .providers
        .iter()
        .any(|provider| provider.required_for_green && provider.status == ProviderStatus::Stale);

    let (status, reason_code, summary) = if !blocked_provider_ids.is_empty() {
        (
            SessionReadinessStatus::Blocked,
            if has_stale_provider {
                "READINESS_PROVIDER_STALE"
            } else {
                "READINESS_PROVIDER_BLOCKED"
            },
            format!(
                "The session is blocked because required readiness providers failed or went stale: {}.",
                blocked_provider_ids.join(", ")
            ),
        )
    } else if !suspect_provider_ids.is_empty() {
        (
            SessionReadinessStatus::Suspect,
            "READINESS_PROVIDER_REVIEW_REQUIRED",
            format!(
                "The session is suspect because required readiness providers need review: {}.",
                suspect_provider_ids.join(", ")
            ),
        )
    } else {
        (
            SessionReadinessStatus::Green,
            "READINESS_READY_TO_ACTIVATE",
            "All required readiness providers passed, so the session is eligible to activate."
                .to_string(),
        )
    };

    let packet_digest = packet_digest(
        request,
        status,
        reason_code,
        &blocked_provider_ids,
        &suspect_provider_ids,
        &[],
    );
    let mut history = request.previous_history.clone();
    history.push(ReadinessHistoryEntry {
        packet_id: request.packet_id.clone(),
        packet_digest: packet_digest.clone(),
        status,
        reason_code: reason_code.to_string(),
        created_at_utc: request.valid_from_utc.clone(),
    });

    SessionReadinessPacket {
        packet_id: request.packet_id.clone(),
        packet_digest,
        deployment_instance_id: request.deployment_instance_id.clone(),
        session_id: request.session_id.clone(),
        valid_from_utc: request.valid_from_utc.clone(),
        valid_to_utc: request.valid_to_utc.clone(),
        source_promotion_packet_id: request.source_promotion_packet_id.clone(),
        status,
        reason_code: reason_code.to_string(),
        retained_artifact_id: format!("readiness_packets/{}.txt", request.packet_id),
        required_provider_kinds: request
            .required_provider_kinds
            .iter()
            .map(|kind| kind.as_str().to_string())
            .collect(),
        missing_required_provider_kinds: Vec::new(),
        blocked_provider_ids,
        suspect_provider_ids,
        providers: request.providers.clone(),
        history,
        summary,
    }
}

/// Writes the request and packet artifacts to the provided directory.
pub fn write_session_readiness_artifacts(
    root: &Path,
    request: &SessionReadinessPacketRequest,
    packet: &SessionReadinessPacket,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(
        root.join("session_readiness_request.txt"),
        render_request(request),
    )?;
    fs::write(
        root.join("session_readiness_packet.txt"),
        render_packet(packet),
    )?;
    Ok(())
}

fn provider(
    provider_id: &str,
    provider_kind: ReadinessProviderKind,
    reason_code: &str,
    summary: &str,
) -> ReadinessProviderOutput {
    ReadinessProviderOutput {
        provider_id: provider_id.to_string(),
        provider_kind,
        status: ProviderStatus::Pass,
        reason_code: reason_code.to_string(),
        summary: summary.to_string(),
        source_artifact_id: format!("evidence/{}.json", provider_id),
        component_digest: fnv1a_hex(&[
            provider_id.to_string(),
            provider_kind.as_str().to_string(),
            reason_code.to_string(),
        ]),
        required_for_green: true,
    }
}

fn base_request() -> SessionReadinessPacketRequest {
    SessionReadinessPacketRequest {
        packet_id: "session-readiness-001".to_string(),
        deployment_instance_id: "deployment-instance-001".to_string(),
        session_id: "globex_2026_03_18".to_string(),
        valid_from_utc: "2026-03-18T14:25:00Z".to_string(),
        valid_to_utc: "2026-03-18T20:00:00Z".to_string(),
        source_promotion_packet_id: "promotion-packet-live-001".to_string(),
        required_provider_kinds: vec![
            ReadinessProviderKind::SessionEligibility,
            ReadinessProviderKind::RuntimeRisk,
            ReadinessProviderKind::BrokerState,
            ReadinessProviderKind::ContractConformance,
            ReadinessProviderKind::AuthoritativeReconciliation,
            ReadinessProviderKind::ActivationLaneHealth,
            ReadinessProviderKind::FeeSnapshot,
            ReadinessProviderKind::MarginSnapshot,
            ReadinessProviderKind::Entitlement,
            ReadinessProviderKind::BackupFreshness,
            ReadinessProviderKind::RestoreDrill,
            ReadinessProviderKind::ClockHealth,
            ReadinessProviderKind::SecretHealth,
            ReadinessProviderKind::LedgerClose,
        ],
        providers: vec![
            provider(
                "session-eligibility-001",
                ReadinessProviderKind::SessionEligibility,
                "SESSION_ELIGIBLE",
                "Compiled session eligibility kept the runtime in a tradeable session slice.",
            ),
            provider(
                "runtime-risk-001",
                ReadinessProviderKind::RuntimeRisk,
                "RUNTIME_RISK_ALLOW",
                "Runtime risk engine kept trading eligibility green.",
            ),
            provider(
                "broker-state-001",
                ReadinessProviderKind::BrokerState,
                "BROKER_STATE_SYNCHRONIZED",
                "Broker session state is synchronized and connected.",
            ),
            provider(
                "contract-conformance-001",
                ReadinessProviderKind::ContractConformance,
                "CONTRACT_CONFORMANCE_VALID",
                "Active contract routing matches the approved execution contract.",
            ),
            provider(
                "reconciliation-001",
                ReadinessProviderKind::AuthoritativeReconciliation,
                "RECONCILIATION_PASS",
                "Authoritative reconciliation kept the session green.",
            ),
            provider(
                "activation-health-001",
                ReadinessProviderKind::ActivationLaneHealth,
                "ACTIVATION_HEALTH_GREEN",
                "Activation-lane health checks are green.",
            ),
            provider(
                "fee-check-001",
                ReadinessProviderKind::FeeSnapshot,
                "FEE_SNAPSHOT_FRESH",
                "Fee schedule snapshot is fresh.",
            ),
            provider(
                "margin-check-001",
                ReadinessProviderKind::MarginSnapshot,
                "MARGIN_SNAPSHOT_FRESH",
                "Margin snapshot is fresh.",
            ),
            provider(
                "entitlement-check-001",
                ReadinessProviderKind::Entitlement,
                "ENTITLEMENT_LIVE",
                "Market-data entitlement is live and current.",
            ),
            provider(
                "backup-check-001",
                ReadinessProviderKind::BackupFreshness,
                "BACKUP_FRESHNESS_GREEN",
                "Backup freshness evidence is green.",
            ),
            provider(
                "restore-check-001",
                ReadinessProviderKind::RestoreDrill,
                "RESTORE_DRILL_GREEN",
                "Restore drill evidence remains fresh enough for activation.",
            ),
            provider(
                "clock-check-001",
                ReadinessProviderKind::ClockHealth,
                "CLOCK_HEALTH_GREEN",
                "Clock discipline is within the approved skew bounds.",
            ),
            provider(
                "secret-check-001",
                ReadinessProviderKind::SecretHealth,
                "SECRET_HEALTH_GREEN",
                "Secrets are mounted and fresh for the runtime lane.",
            ),
            provider(
                "ledger-close-001",
                ReadinessProviderKind::LedgerClose,
                "LEDGER_CLOSE_GREEN",
                "Ledger-close evidence is clean and bound to the current session.",
            ),
        ],
        previous_history: vec![ReadinessHistoryEntry {
            packet_id: "session-readiness-000".to_string(),
            packet_digest: "history000digest".to_string(),
            status: SessionReadinessStatus::Blocked,
            reason_code: "READINESS_PROVIDER_BLOCKED".to_string(),
            created_at_utc: "2026-03-17T14:25:00Z".to_string(),
        }],
        correlation_id: "readiness-correlation-001".to_string(),
        operator_summary: "Assemble the next-session readiness packet for the live lane."
            .to_string(),
    }
}

/// Built-in readiness-packet scenarios used by tests and smoke drills.
pub fn sample_session_readiness_request(name: &str) -> Option<SessionReadinessPacketRequest> {
    let mut request = base_request();
    match name {
        "green-readiness-pass" => Some(request),
        "clock-stale-blocked" => {
            request.packet_id = "session-readiness-clock-stale".to_string();
            if let Some(provider) = request
                .providers
                .iter_mut()
                .find(|provider| provider.provider_kind == ReadinessProviderKind::ClockHealth)
            {
                provider.status = ProviderStatus::Stale;
                provider.reason_code = "CLOCK_HEALTH_STALE".to_string();
                provider.summary =
                    "Clock discipline evidence is stale and blocks session activation.".to_string();
            }
            Some(request)
        }
        "broker-state-blocked" => {
            request.packet_id = "session-readiness-broker-blocked".to_string();
            if let Some(provider) = request
                .providers
                .iter_mut()
                .find(|provider| provider.provider_kind == ReadinessProviderKind::BrokerState)
            {
                provider.status = ProviderStatus::Blocked;
                provider.reason_code = "BROKER_STATE_BLOCKED".to_string();
                provider.summary =
                    "Broker session state is blocked and prevents readiness issuance.".to_string();
            }
            Some(request)
        }
        "reconciliation-review-required" => {
            request.packet_id = "session-readiness-recon-review".to_string();
            if let Some(provider) = request.providers.iter_mut().find(|provider| {
                provider.provider_kind == ReadinessProviderKind::AuthoritativeReconciliation
            }) {
                provider.status = ProviderStatus::ReviewRequired;
                provider.reason_code = "RECONCILIATION_REVIEW_REQUIRED".to_string();
                provider.summary =
                    "Authoritative reconciliation requires operator review before activation."
                        .to_string();
            }
            Some(request)
        }
        "missing-secret-provider-invalid" => {
            request.packet_id = "session-readiness-missing-secret".to_string();
            request
                .providers
                .retain(|provider| provider.provider_kind != ReadinessProviderKind::SecretHealth);
            Some(request)
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{
        SessionReadinessStatus, assemble_session_readiness_packet, sample_session_readiness_request,
    };

    #[test]
    fn green_packet_keeps_history_and_no_blocks() {
        let request = sample_session_readiness_request("green-readiness-pass")
            .expect("green scenario exists");
        let packet = assemble_session_readiness_packet(&request);

        assert_eq!(SessionReadinessStatus::Green, packet.status);
        assert_eq!("READINESS_READY_TO_ACTIVATE", packet.reason_code);
        assert!(packet.blocked_provider_ids.is_empty());
        assert!(packet.suspect_provider_ids.is_empty());
        assert_eq!(2, packet.history.len());
    }

    #[test]
    fn stale_required_provider_blocks_session() {
        let request = sample_session_readiness_request("clock-stale-blocked")
            .expect("clock stale scenario exists");
        let packet = assemble_session_readiness_packet(&request);

        assert_eq!(SessionReadinessStatus::Blocked, packet.status);
        assert_eq!("READINESS_PROVIDER_STALE", packet.reason_code);
        assert_eq!(
            vec!["clock-check-001".to_string()],
            packet.blocked_provider_ids
        );
    }

    #[test]
    fn blocked_required_provider_blocks_session() {
        let request = sample_session_readiness_request("broker-state-blocked")
            .expect("broker blocked scenario exists");
        let packet = assemble_session_readiness_packet(&request);

        assert_eq!(SessionReadinessStatus::Blocked, packet.status);
        assert_eq!("READINESS_PROVIDER_BLOCKED", packet.reason_code);
        assert_eq!(
            vec!["broker-state-001".to_string()],
            packet.blocked_provider_ids
        );
    }

    #[test]
    fn review_required_provider_marks_packet_suspect() {
        let request = sample_session_readiness_request("reconciliation-review-required")
            .expect("review scenario exists");
        let packet = assemble_session_readiness_packet(&request);

        assert_eq!(SessionReadinessStatus::Suspect, packet.status);
        assert_eq!("READINESS_PROVIDER_REVIEW_REQUIRED", packet.reason_code);
        assert_eq!(
            vec!["reconciliation-001".to_string()],
            packet.suspect_provider_ids
        );
    }

    #[test]
    fn missing_required_provider_invalidates_packet() {
        let request = sample_session_readiness_request("missing-secret-provider-invalid")
            .expect("missing secret scenario exists");
        let packet = assemble_session_readiness_packet(&request);

        assert_eq!(SessionReadinessStatus::Invalid, packet.status);
        assert_eq!("READINESS_REQUIRED_PROVIDER_MISSING", packet.reason_code);
        assert_eq!(
            vec!["secret_health".to_string()],
            packet.missing_required_provider_kinds
        );
    }
}
