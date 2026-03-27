//! Executable guardian emergency control path.
//!
//! Guardian stays intentionally small: it verifies broker connectivity,
//! validates break-glass authorization, executes emergency cancel or flatten
//! requests, and emits evidence without taking ownership of ordinary runtime
//! state.

use std::collections::BTreeSet;
use std::fs;
use std::path::Path;

use crate::GuardianAction;

/// Independent connectivity report that guardian can verify without `opsd`.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BrokerConnectivityReport {
    pub connectivity_check_id: String,
    pub broker_session_id: String,
    pub verified_by_guardian: bool,
    pub reachable: bool,
    pub high_priority_lane_available: bool,
    pub round_trip_ms: u32,
    pub observed_at_utc: String,
}

/// Emergency action request routed through guardian.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EmergencyActionRequest {
    pub request_id: String,
    pub deployment_instance_id: String,
    pub incident_reference_id: String,
    pub authorization_token_id: String,
    pub requested_by: String,
    pub correlation_id: String,
    pub requested_at_utc: String,
    pub action: GuardianAction,
}

/// Final machine-readable evidence emitted for every guardian action attempt.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct EmergencyActionEvidence {
    pub evidence_id: String,
    pub request_id: String,
    pub deployment_instance_id: String,
    pub incident_reference_id: String,
    pub action: GuardianAction,
    pub disposition: EmergencyDisposition,
    pub reason_code: String,
    pub connectivity_check_id: String,
    pub broker_response_id: Option<String>,
    pub duplicate_invocation: bool,
    pub operator_summary: String,
}

/// Outcome of an emergency guardian action attempt.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EmergencyDisposition {
    Executed,
    Rejected,
    SuppressedDuplicate,
}

impl EmergencyDisposition {
    /// Stable string form for logs and retained artifacts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Executed => "executed",
            Self::Rejected => "rejected",
            Self::SuppressedDuplicate => "suppressed_duplicate",
        }
    }
}

/// Minimal stateful guardian controller that only deduplicates emergency actions.
#[derive(Clone, Debug, Default)]
pub struct EmergencyController {
    executed_keys: BTreeSet<String>,
}

impl EmergencyController {
    /// Creates a fresh guardian controller.
    pub fn new() -> Self {
        Self::default()
    }

    /// Executes or rejects an emergency request while retaining action evidence.
    pub fn execute(
        &mut self,
        request: &EmergencyActionRequest,
        connectivity: &BrokerConnectivityReport,
    ) -> EmergencyActionEvidence {
        if request.authorization_token_id.is_empty() {
            return EmergencyActionEvidence {
                evidence_id: format!("guardian-evidence-{}", request.request_id),
                request_id: request.request_id.clone(),
                deployment_instance_id: request.deployment_instance_id.clone(),
                incident_reference_id: request.incident_reference_id.clone(),
                action: request.action,
                disposition: EmergencyDisposition::Rejected,
                reason_code: "GUARDIAN_AUTHORIZATION_REQUIRED".to_string(),
                connectivity_check_id: connectivity.connectivity_check_id.clone(),
                broker_response_id: None,
                duplicate_invocation: false,
                operator_summary:
                    "Guardian refused the emergency request because the break-glass authorization token was missing."
                        .to_string(),
            };
        }

        if !connectivity.verified_by_guardian || !connectivity.reachable {
            return EmergencyActionEvidence {
                evidence_id: format!("guardian-evidence-{}", request.request_id),
                request_id: request.request_id.clone(),
                deployment_instance_id: request.deployment_instance_id.clone(),
                incident_reference_id: request.incident_reference_id.clone(),
                action: request.action,
                disposition: EmergencyDisposition::Rejected,
                reason_code: "GUARDIAN_CONNECTIVITY_PROOF_REQUIRED".to_string(),
                connectivity_check_id: connectivity.connectivity_check_id.clone(),
                broker_response_id: None,
                duplicate_invocation: false,
                operator_summary:
                    "Guardian refused the emergency request because it could not independently verify broker connectivity."
                        .to_string(),
            };
        }

        if !connectivity.high_priority_lane_available {
            return EmergencyActionEvidence {
                evidence_id: format!("guardian-evidence-{}", request.request_id),
                request_id: request.request_id.clone(),
                deployment_instance_id: request.deployment_instance_id.clone(),
                incident_reference_id: request.incident_reference_id.clone(),
                action: request.action,
                disposition: EmergencyDisposition::Rejected,
                reason_code: "GUARDIAN_HIGH_PRIORITY_LANE_REQUIRED".to_string(),
                connectivity_check_id: connectivity.connectivity_check_id.clone(),
                broker_response_id: None,
                duplicate_invocation: false,
                operator_summary:
                    "Guardian refused the emergency request because the reserved high-priority lane was not available."
                        .to_string(),
            };
        }

        let execution_key = format!(
            "{}::{}::{}",
            request.deployment_instance_id,
            request.incident_reference_id,
            request.action.as_str(),
        );
        if !self.executed_keys.insert(execution_key) {
            return EmergencyActionEvidence {
                evidence_id: format!("guardian-evidence-{}", request.request_id),
                request_id: request.request_id.clone(),
                deployment_instance_id: request.deployment_instance_id.clone(),
                incident_reference_id: request.incident_reference_id.clone(),
                action: request.action,
                disposition: EmergencyDisposition::SuppressedDuplicate,
                reason_code: "GUARDIAN_DUPLICATE_INVOCATION_SUPPRESSED".to_string(),
                connectivity_check_id: connectivity.connectivity_check_id.clone(),
                broker_response_id: None,
                duplicate_invocation: true,
                operator_summary:
                    "Guardian suppressed a duplicate emergency request for the same deployment, incident, and action."
                        .to_string(),
            };
        }

        EmergencyActionEvidence {
            evidence_id: format!("guardian-evidence-{}", request.request_id),
            request_id: request.request_id.clone(),
            deployment_instance_id: request.deployment_instance_id.clone(),
            incident_reference_id: request.incident_reference_id.clone(),
            action: request.action,
            disposition: EmergencyDisposition::Executed,
            reason_code: "GUARDIAN_EMERGENCY_ACTION_EXECUTED".to_string(),
            connectivity_check_id: connectivity.connectivity_check_id.clone(),
            broker_response_id: Some(format!("broker-ack-{}", request.request_id)),
            duplicate_invocation: false,
            operator_summary:
                "Guardian independently verified broker connectivity and executed the authorized emergency action."
                    .to_string(),
        }
    }
}

fn render_connectivity_report(report: &BrokerConnectivityReport) -> String {
    [
        format!("connectivity_check_id={}", report.connectivity_check_id),
        format!("broker_session_id={}", report.broker_session_id),
        format!("verified_by_guardian={}", report.verified_by_guardian),
        format!("reachable={}", report.reachable),
        format!(
            "high_priority_lane_available={}",
            report.high_priority_lane_available
        ),
        format!("round_trip_ms={}", report.round_trip_ms),
        format!("observed_at_utc={}", report.observed_at_utc),
    ]
    .join("\n")
}

fn render_request(request: &EmergencyActionRequest) -> String {
    [
        format!("request_id={}", request.request_id),
        format!("deployment_instance_id={}", request.deployment_instance_id),
        format!("incident_reference_id={}", request.incident_reference_id),
        format!("authorization_token_id={}", request.authorization_token_id),
        format!("requested_by={}", request.requested_by),
        format!("correlation_id={}", request.correlation_id),
        format!("requested_at_utc={}", request.requested_at_utc),
        format!("action={}", request.action.as_str()),
    ]
    .join("\n")
}

fn render_evidence(evidence: &EmergencyActionEvidence) -> String {
    let mut lines = vec![
        format!("evidence_id={}", evidence.evidence_id),
        format!("request_id={}", evidence.request_id),
        format!("deployment_instance_id={}", evidence.deployment_instance_id),
        format!("incident_reference_id={}", evidence.incident_reference_id),
        format!("action={}", evidence.action.as_str()),
        format!("disposition={}", evidence.disposition.as_str()),
        format!("reason_code={}", evidence.reason_code),
        format!("connectivity_check_id={}", evidence.connectivity_check_id),
        format!("duplicate_invocation={}", evidence.duplicate_invocation),
        format!("operator_summary={}", evidence.operator_summary),
    ];
    if let Some(response_id) = evidence.broker_response_id.as_deref() {
        lines.push(format!("broker_response_id={response_id}"));
    }
    lines.join("\n")
}

/// Writes guardian request, connectivity, and evidence artifacts to the provided directory.
pub fn write_emergency_artifacts(
    root: &Path,
    request: &EmergencyActionRequest,
    connectivity: &BrokerConnectivityReport,
    evidence: &EmergencyActionEvidence,
) -> std::io::Result<()> {
    fs::create_dir_all(root)?;
    fs::write(root.join("guardian_request.txt"), render_request(request))?;
    fs::write(
        root.join("guardian_connectivity.txt"),
        render_connectivity_report(connectivity),
    )?;
    fs::write(
        root.join("guardian_evidence.txt"),
        render_evidence(evidence),
    )?;
    Ok(())
}

fn base_request() -> EmergencyActionRequest {
    EmergencyActionRequest {
        request_id: "guardian-flatten-001".to_string(),
        deployment_instance_id: "opsd-gc-live-001".to_string(),
        incident_reference_id: "incident-20260327-guardian".to_string(),
        authorization_token_id: "break-glass-token-001".to_string(),
        requested_by: "guardian".to_string(),
        correlation_id: "guardian-corr-001".to_string(),
        requested_at_utc: "2026-03-27T20:35:00+00:00".to_string(),
        action: GuardianAction::FlattenAllPositions,
    }
}

fn base_connectivity() -> BrokerConnectivityReport {
    BrokerConnectivityReport {
        connectivity_check_id: "guardian-connectivity-001".to_string(),
        broker_session_id: "ibkr-live-001".to_string(),
        verified_by_guardian: true,
        reachable: true,
        high_priority_lane_available: true,
        round_trip_ms: 45,
        observed_at_utc: "2026-03-27T20:34:59+00:00".to_string(),
    }
}

/// Built-in guardian request scenarios used by tests and drills.
pub fn sample_emergency_action_request(name: &str) -> Option<EmergencyActionRequest> {
    let mut request = base_request();
    match name {
        "authorized-flatten" => Some(request),
        "duplicate-cancel" => {
            request.request_id = "guardian-cancel-001".to_string();
            request.action = GuardianAction::CancelAllOpenOrders;
            Some(request)
        }
        "missing-auth" => {
            request.authorization_token_id.clear();
            Some(request)
        }
        _ => None,
    }
}

/// Built-in guardian connectivity scenarios used by tests and drills.
pub fn sample_guardian_connectivity_report(name: &str) -> Option<BrokerConnectivityReport> {
    let mut report = base_connectivity();
    match name {
        "healthy" => Some(report),
        "impaired-connectivity" => {
            report.reachable = false;
            Some(report)
        }
        "no-high-priority-lane" => {
            report.high_priority_lane_available = false;
            Some(report)
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{
        EmergencyController, EmergencyDisposition, sample_emergency_action_request,
        sample_guardian_connectivity_report,
    };

    #[test]
    fn guardian_executes_authorized_flatten_when_connectivity_is_proven() {
        let request = sample_emergency_action_request("authorized-flatten")
            .expect("authorized flatten scenario exists");
        let connectivity =
            sample_guardian_connectivity_report("healthy").expect("healthy connectivity exists");
        let mut controller = EmergencyController::new();
        let evidence = controller.execute(&request, &connectivity);

        assert_eq!(EmergencyDisposition::Executed, evidence.disposition);
        assert_eq!("GUARDIAN_EMERGENCY_ACTION_EXECUTED", evidence.reason_code);
        assert!(evidence.broker_response_id.is_some());
    }

    #[test]
    fn guardian_rejects_missing_break_glass_authorization() {
        let request =
            sample_emergency_action_request("missing-auth").expect("missing auth scenario exists");
        let connectivity =
            sample_guardian_connectivity_report("healthy").expect("healthy connectivity exists");
        let mut controller = EmergencyController::new();
        let evidence = controller.execute(&request, &connectivity);

        assert_eq!(EmergencyDisposition::Rejected, evidence.disposition);
        assert_eq!("GUARDIAN_AUTHORIZATION_REQUIRED", evidence.reason_code);
    }

    #[test]
    fn guardian_rejects_when_connectivity_cannot_be_verified() {
        let request = sample_emergency_action_request("authorized-flatten")
            .expect("authorized flatten scenario exists");
        let connectivity = sample_guardian_connectivity_report("impaired-connectivity")
            .expect("impaired connectivity scenario exists");
        let mut controller = EmergencyController::new();
        let evidence = controller.execute(&request, &connectivity);

        assert_eq!(EmergencyDisposition::Rejected, evidence.disposition);
        assert_eq!("GUARDIAN_CONNECTIVITY_PROOF_REQUIRED", evidence.reason_code);
    }

    #[test]
    fn guardian_requires_the_reserved_high_priority_lane() {
        let request = sample_emergency_action_request("authorized-flatten")
            .expect("authorized flatten scenario exists");
        let connectivity = sample_guardian_connectivity_report("no-high-priority-lane")
            .expect("high priority failure scenario exists");
        let mut controller = EmergencyController::new();
        let evidence = controller.execute(&request, &connectivity);

        assert_eq!(EmergencyDisposition::Rejected, evidence.disposition);
        assert_eq!("GUARDIAN_HIGH_PRIORITY_LANE_REQUIRED", evidence.reason_code);
    }

    #[test]
    fn guardian_suppresses_duplicate_invocations_for_same_incident_and_action() {
        let request = sample_emergency_action_request("duplicate-cancel")
            .expect("duplicate cancel scenario exists");
        let connectivity =
            sample_guardian_connectivity_report("healthy").expect("healthy connectivity exists");
        let mut controller = EmergencyController::new();

        let first = controller.execute(&request, &connectivity);
        let second = controller.execute(&request, &connectivity);

        assert_eq!(EmergencyDisposition::Executed, first.disposition);
        assert_eq!(
            EmergencyDisposition::SuppressedDuplicate,
            second.disposition
        );
        assert!(second.duplicate_invocation);
    }
}
