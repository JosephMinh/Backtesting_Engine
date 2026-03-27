use std::collections::BTreeSet;

/// Calendar classification carried into the compiled runtime schedule artifact.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SessionDayKind {
    Regular,
    EarlyClose,
    HolidayClosure,
}

impl SessionDayKind {
    /// Stable identifier for logs and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Regular => "regular",
            Self::EarlyClose => "early_close",
            Self::HolidayClosure => "holiday_closure",
        }
    }
}

/// Compiled session state that the runtime may act on directly.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CompiledSessionState {
    Tradeable,
    Maintenance,
    ResetBoundary,
    DeliveryFence,
    PolicyRestricted,
    HolidayClosure,
    Closed,
}

impl CompiledSessionState {
    /// Stable identifier for logs and smoke scripts.
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Tradeable => "tradeable",
            Self::Maintenance => "maintenance",
            Self::ResetBoundary => "reset_boundary",
            Self::DeliveryFence => "delivery_fence",
            Self::PolicyRestricted => "policy_restricted",
            Self::HolidayClosure => "holiday_closure",
            Self::Closed => "closed",
        }
    }

    /// Whether the compiled state allows new economic activity.
    pub const fn is_tradeable(self) -> bool {
        matches!(self, Self::Tradeable)
    }
}

/// Calendar entry compiled from product-profile and exchange-session inputs.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SessionCalendarEntry {
    pub entry_id: String,
    pub session_id: String,
    pub trade_date: String,
    pub calendar_id: String,
    pub open_utc: String,
    pub close_utc: String,
    pub kind: SessionDayKind,
    pub exchange_offset_minutes: i16,
    pub local_open_label: String,
    pub local_close_label: String,
}

impl SessionCalendarEntry {
    /// Creates a new session-calendar entry.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        entry_id: impl Into<String>,
        session_id: impl Into<String>,
        trade_date: impl Into<String>,
        calendar_id: impl Into<String>,
        open_utc: impl Into<String>,
        close_utc: impl Into<String>,
        kind: SessionDayKind,
        exchange_offset_minutes: i16,
        local_open_label: impl Into<String>,
        local_close_label: impl Into<String>,
    ) -> Self {
        Self {
            entry_id: entry_id.into(),
            session_id: session_id.into(),
            trade_date: trade_date.into(),
            calendar_id: calendar_id.into(),
            open_utc: open_utc.into(),
            close_utc: close_utc.into(),
            kind,
            exchange_offset_minutes,
            local_open_label: local_open_label.into(),
            local_close_label: local_close_label.into(),
        }
    }

    fn covers_slice(&self, start_utc: &str, end_utc: &str) -> bool {
        self.open_utc.as_str() <= start_utc && self.close_utc.as_str() >= end_utc
    }
}

/// Maintenance-window definition admitted by the product profile.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MaintenanceWindowDefinition {
    pub window_id: String,
    pub policy_window_id: String,
    pub start_utc: String,
    pub end_utc: String,
    pub reason_code: String,
}

impl MaintenanceWindowDefinition {
    pub fn new(
        window_id: impl Into<String>,
        policy_window_id: impl Into<String>,
        start_utc: impl Into<String>,
        end_utc: impl Into<String>,
        reason_code: impl Into<String>,
    ) -> Self {
        Self {
            window_id: window_id.into(),
            policy_window_id: policy_window_id.into(),
            start_utc: start_utc.into(),
            end_utc: end_utc.into(),
            reason_code: reason_code.into(),
        }
    }

    fn covers_slice(&self, start_utc: &str, end_utc: &str) -> bool {
        self.start_utc.as_str() <= start_utc && self.end_utc.as_str() >= end_utc
    }
}

/// Delivery-fence restriction derived from reviewed roll and contract rules.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct DeliveryFenceWindowDefinition {
    pub window_id: String,
    pub delivery_fence_rule: String,
    pub delivery_fence_input: String,
    pub start_utc: String,
    pub end_utc: String,
    pub reason_code: String,
}

impl DeliveryFenceWindowDefinition {
    pub fn new(
        window_id: impl Into<String>,
        delivery_fence_rule: impl Into<String>,
        delivery_fence_input: impl Into<String>,
        start_utc: impl Into<String>,
        end_utc: impl Into<String>,
        reason_code: impl Into<String>,
    ) -> Self {
        Self {
            window_id: window_id.into(),
            delivery_fence_rule: delivery_fence_rule.into(),
            delivery_fence_input: delivery_fence_input.into(),
            start_utc: start_utc.into(),
            end_utc: end_utc.into(),
            reason_code: reason_code.into(),
        }
    }

    fn covers_slice(&self, start_utc: &str, end_utc: &str) -> bool {
        self.start_utc.as_str() <= start_utc && self.end_utc.as_str() >= end_utc
    }
}

/// Policy overlay admitted from resolved context and runtime overlays.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PolicyOverlayWindowDefinition {
    pub window_id: String,
    pub overlay_source: String,
    pub start_utc: String,
    pub end_utc: String,
    pub state: CompiledSessionState,
    pub reason_code: String,
}

impl PolicyOverlayWindowDefinition {
    pub fn new(
        window_id: impl Into<String>,
        overlay_source: impl Into<String>,
        start_utc: impl Into<String>,
        end_utc: impl Into<String>,
        state: CompiledSessionState,
        reason_code: impl Into<String>,
    ) -> Self {
        Self {
            window_id: window_id.into(),
            overlay_source: overlay_source.into(),
            start_utc: start_utc.into(),
            end_utc: end_utc.into(),
            state,
            reason_code: reason_code.into(),
        }
    }

    fn covers_slice(&self, start_utc: &str, end_utc: &str) -> bool {
        self.start_utc.as_str() <= start_utc && self.end_utc.as_str() >= end_utc
    }
}

/// Product-profile and resolved-context inputs consumed by the compiler.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ScheduleCompileRequest {
    pub artifact_id: String,
    pub product_profile_id: String,
    pub symbol: String,
    pub calendar_id: String,
    pub exchange_timezone: String,
    pub exchange_calendar_source: String,
    pub event_window_source: String,
    pub maintenance_window_ids: Vec<String>,
    pub delivery_fence_rule: String,
    pub delivery_fence_input: String,
    pub generated_at_utc: String,
    pub session_calendar_entries: Vec<SessionCalendarEntry>,
    pub maintenance_windows: Vec<MaintenanceWindowDefinition>,
    pub delivery_fence_windows: Vec<DeliveryFenceWindowDefinition>,
    pub policy_overlay_windows: Vec<PolicyOverlayWindowDefinition>,
}

impl ScheduleCompileRequest {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        artifact_id: impl Into<String>,
        product_profile_id: impl Into<String>,
        symbol: impl Into<String>,
        calendar_id: impl Into<String>,
        exchange_timezone: impl Into<String>,
        exchange_calendar_source: impl Into<String>,
        event_window_source: impl Into<String>,
        maintenance_window_ids: Vec<String>,
        delivery_fence_rule: impl Into<String>,
        delivery_fence_input: impl Into<String>,
        generated_at_utc: impl Into<String>,
        session_calendar_entries: Vec<SessionCalendarEntry>,
        maintenance_windows: Vec<MaintenanceWindowDefinition>,
        delivery_fence_windows: Vec<DeliveryFenceWindowDefinition>,
        policy_overlay_windows: Vec<PolicyOverlayWindowDefinition>,
    ) -> Self {
        Self {
            artifact_id: artifact_id.into(),
            product_profile_id: product_profile_id.into(),
            symbol: symbol.into(),
            calendar_id: calendar_id.into(),
            exchange_timezone: exchange_timezone.into(),
            exchange_calendar_source: exchange_calendar_source.into(),
            event_window_source: event_window_source.into(),
            maintenance_window_ids,
            delivery_fence_rule: delivery_fence_rule.into(),
            delivery_fence_input: delivery_fence_input.into(),
            generated_at_utc: generated_at_utc.into(),
            session_calendar_entries,
            maintenance_windows,
            delivery_fence_windows,
            policy_overlay_windows,
        }
    }
}

/// Inspectable compiled slice retained by the runtime.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CompiledSessionSlice {
    pub slice_id: String,
    pub session_id: Option<String>,
    pub trade_date: Option<String>,
    pub start_utc: String,
    pub end_utc: String,
    pub state: CompiledSessionState,
    pub reason_code: String,
    pub source_ids: Vec<String>,
    pub exchange_offset_minutes: i16,
    pub local_open_label: Option<String>,
    pub local_close_label: Option<String>,
}

/// Canonical compiled schedule artifact consumed by the runtime.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CompiledSessionArtifact {
    pub artifact_id: String,
    pub retained_artifact_id: String,
    pub product_profile_id: String,
    pub symbol: String,
    pub calendar_id: String,
    pub exchange_timezone: String,
    pub exchange_calendar_source: String,
    pub event_window_source: String,
    pub maintenance_window_ids: Vec<String>,
    pub delivery_fence_rule: String,
    pub delivery_fence_input: String,
    pub generated_at_utc: String,
    pub compiled_from_utc: String,
    pub compiled_to_utc: String,
    pub slices: Vec<CompiledSessionSlice>,
}

impl CompiledSessionArtifact {
    /// Returns the number of tradeable slices in the artifact.
    pub fn tradeable_slice_count(&self) -> usize {
        self.slices
            .iter()
            .filter(|slice| slice.state == CompiledSessionState::Tradeable)
            .count()
    }

    /// Evaluates a UTC-normalized timestamp against the compiled schedule.
    pub fn evaluate_at(
        &self,
        evaluated_at_utc: &str,
    ) -> Result<SessionTopologyDecision, ScheduleError> {
        validate_utc_timestamp("evaluated_at_utc", evaluated_at_utc)?;
        if evaluated_at_utc < self.compiled_from_utc.as_str()
            || evaluated_at_utc >= self.compiled_to_utc.as_str()
        {
            return Err(ScheduleError::TimestampOutsideCompiledRange {
                evaluated_at_utc: evaluated_at_utc.to_string(),
                compiled_from_utc: self.compiled_from_utc.clone(),
                compiled_to_utc: self.compiled_to_utc.clone(),
            });
        }
        let Some(slice) = self.slices.iter().find(|slice| {
            slice.start_utc.as_str() <= evaluated_at_utc
                && slice.end_utc.as_str() > evaluated_at_utc
        }) else {
            return Err(ScheduleError::MissingCompiledSlice {
                evaluated_at_utc: evaluated_at_utc.to_string(),
            });
        };
        Ok(SessionTopologyDecision {
            artifact_id: self.artifact_id.clone(),
            retained_artifact_id: self.retained_artifact_id.clone(),
            evaluated_at_utc: evaluated_at_utc.to_string(),
            session_id: slice.session_id.clone(),
            trade_date: slice.trade_date.clone(),
            state: slice.state,
            tradeable: slice.state.is_tradeable(),
            reason_code: slice.reason_code.clone(),
            matched_slice_id: slice.slice_id.clone(),
            source_ids: slice.source_ids.clone(),
            exchange_offset_minutes: slice.exchange_offset_minutes,
            local_open_label: slice.local_open_label.clone(),
            local_close_label: slice.local_close_label.clone(),
        })
    }
}

/// Result of evaluating a moment against the compiled session topology.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SessionTopologyDecision {
    pub artifact_id: String,
    pub retained_artifact_id: String,
    pub evaluated_at_utc: String,
    pub session_id: Option<String>,
    pub trade_date: Option<String>,
    pub state: CompiledSessionState,
    pub tradeable: bool,
    pub reason_code: String,
    pub matched_slice_id: String,
    pub source_ids: Vec<String>,
    pub exchange_offset_minutes: i16,
    pub local_open_label: Option<String>,
    pub local_close_label: Option<String>,
}

/// Compiler and evaluation failures surfaced back to the runtime.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ScheduleError {
    EmptyCalendar {
        calendar_id: String,
    },
    InvalidTimestamp {
        field: &'static str,
        value: String,
    },
    InvertedWindow {
        label: &'static str,
        start_utc: String,
        end_utc: String,
    },
    CalendarMismatch {
        expected: String,
        actual: String,
    },
    OverlappingSessionEntries {
        previous_entry_id: String,
        next_entry_id: String,
    },
    UnapprovedMaintenanceWindow {
        window_id: String,
        policy_window_id: String,
    },
    DeliveryFenceMismatch {
        window_id: String,
        expected_rule: String,
        actual_rule: String,
        expected_input: String,
        actual_input: String,
    },
    InvalidPolicyOverlayState {
        window_id: String,
        state: CompiledSessionState,
    },
    TimestampOutsideCompiledRange {
        evaluated_at_utc: String,
        compiled_from_utc: String,
        compiled_to_utc: String,
    },
    MissingCompiledSlice {
        evaluated_at_utc: String,
    },
}

/// Compiles the runtime schedule artifact from explicit policy inputs.
pub fn compile_schedule(
    request: ScheduleCompileRequest,
) -> Result<CompiledSessionArtifact, ScheduleError> {
    validate_utc_timestamp("generated_at_utc", &request.generated_at_utc)?;
    if request.session_calendar_entries.is_empty() {
        return Err(ScheduleError::EmptyCalendar {
            calendar_id: request.calendar_id,
        });
    }

    let mut entries = request.session_calendar_entries;
    entries.sort_by(|left, right| left.open_utc.cmp(&right.open_utc));
    for entry in &entries {
        validate_utc_timestamp("session_open_utc", &entry.open_utc)?;
        validate_utc_timestamp("session_close_utc", &entry.close_utc)?;
        validate_interval("session_calendar_entry", &entry.open_utc, &entry.close_utc)?;
        if entry.calendar_id != request.calendar_id {
            return Err(ScheduleError::CalendarMismatch {
                expected: request.calendar_id.clone(),
                actual: entry.calendar_id.clone(),
            });
        }
    }
    for pair in entries.windows(2) {
        if pair[0].close_utc.as_str() > pair[1].open_utc.as_str() {
            return Err(ScheduleError::OverlappingSessionEntries {
                previous_entry_id: pair[0].entry_id.clone(),
                next_entry_id: pair[1].entry_id.clone(),
            });
        }
    }

    let approved_maintenance_ids = request
        .maintenance_window_ids
        .iter()
        .map(String::as_str)
        .collect::<BTreeSet<_>>();
    for window in &request.maintenance_windows {
        validate_utc_timestamp("maintenance_start_utc", &window.start_utc)?;
        validate_utc_timestamp("maintenance_end_utc", &window.end_utc)?;
        validate_interval("maintenance_window", &window.start_utc, &window.end_utc)?;
        if !approved_maintenance_ids.contains(window.policy_window_id.as_str()) {
            return Err(ScheduleError::UnapprovedMaintenanceWindow {
                window_id: window.window_id.clone(),
                policy_window_id: window.policy_window_id.clone(),
            });
        }
    }

    for window in &request.delivery_fence_windows {
        validate_utc_timestamp("delivery_fence_start_utc", &window.start_utc)?;
        validate_utc_timestamp("delivery_fence_end_utc", &window.end_utc)?;
        validate_interval("delivery_fence_window", &window.start_utc, &window.end_utc)?;
        if window.delivery_fence_rule != request.delivery_fence_rule
            || window.delivery_fence_input != request.delivery_fence_input
        {
            return Err(ScheduleError::DeliveryFenceMismatch {
                window_id: window.window_id.clone(),
                expected_rule: request.delivery_fence_rule.clone(),
                actual_rule: window.delivery_fence_rule.clone(),
                expected_input: request.delivery_fence_input.clone(),
                actual_input: window.delivery_fence_input.clone(),
            });
        }
    }

    for window in &request.policy_overlay_windows {
        validate_utc_timestamp("policy_overlay_start_utc", &window.start_utc)?;
        validate_utc_timestamp("policy_overlay_end_utc", &window.end_utc)?;
        validate_interval("policy_overlay_window", &window.start_utc, &window.end_utc)?;
        if !matches!(
            window.state,
            CompiledSessionState::ResetBoundary | CompiledSessionState::PolicyRestricted
        ) {
            return Err(ScheduleError::InvalidPolicyOverlayState {
                window_id: window.window_id.clone(),
                state: window.state,
            });
        }
    }

    let mut boundaries = BTreeSet::new();
    for entry in &entries {
        boundaries.insert(entry.open_utc.clone());
        boundaries.insert(entry.close_utc.clone());
    }
    for window in &request.maintenance_windows {
        boundaries.insert(window.start_utc.clone());
        boundaries.insert(window.end_utc.clone());
    }
    for window in &request.delivery_fence_windows {
        boundaries.insert(window.start_utc.clone());
        boundaries.insert(window.end_utc.clone());
    }
    for window in &request.policy_overlay_windows {
        boundaries.insert(window.start_utc.clone());
        boundaries.insert(window.end_utc.clone());
    }
    let ordered_boundaries = boundaries.into_iter().collect::<Vec<_>>();
    let compiled_from_utc = ordered_boundaries
        .first()
        .expect("non-empty calendar must create at least one boundary")
        .clone();
    let compiled_to_utc = ordered_boundaries
        .last()
        .expect("non-empty calendar must create at least one boundary")
        .clone();

    let mut raw_slices = Vec::new();
    for (index, boundary_pair) in ordered_boundaries.windows(2).enumerate() {
        let start_utc = boundary_pair[0].clone();
        let end_utc = boundary_pair[1].clone();
        if start_utc == end_utc {
            continue;
        }

        let active_entry = entries
            .iter()
            .find(|entry| entry.covers_slice(&start_utc, &end_utc));
        let active_maintenance = request
            .maintenance_windows
            .iter()
            .filter(|window| window.covers_slice(&start_utc, &end_utc))
            .collect::<Vec<_>>();
        let active_delivery = request
            .delivery_fence_windows
            .iter()
            .filter(|window| window.covers_slice(&start_utc, &end_utc))
            .collect::<Vec<_>>();
        let active_reset = request
            .policy_overlay_windows
            .iter()
            .filter(|window| {
                window.state == CompiledSessionState::ResetBoundary
                    && window.covers_slice(&start_utc, &end_utc)
            })
            .collect::<Vec<_>>();
        let active_policy = request
            .policy_overlay_windows
            .iter()
            .filter(|window| {
                window.state == CompiledSessionState::PolicyRestricted
                    && window.covers_slice(&start_utc, &end_utc)
            })
            .collect::<Vec<_>>();

        let (
            state,
            reason_code,
            session_id,
            trade_date,
            exchange_offset_minutes,
            local_open_label,
            local_close_label,
            source_ids,
        ) = if let Some(entry) = active_entry {
            if entry.kind == SessionDayKind::HolidayClosure {
                (
                    CompiledSessionState::HolidayClosure,
                    "HOLIDAY_EXCHANGE_CLOSED".to_string(),
                    Some(entry.session_id.clone()),
                    Some(entry.trade_date.clone()),
                    entry.exchange_offset_minutes,
                    Some(entry.local_open_label.clone()),
                    Some(entry.local_close_label.clone()),
                    vec![entry.entry_id.clone()],
                )
            } else if !active_maintenance.is_empty() {
                (
                    CompiledSessionState::Maintenance,
                    active_maintenance[0].reason_code.clone(),
                    Some(entry.session_id.clone()),
                    Some(entry.trade_date.clone()),
                    entry.exchange_offset_minutes,
                    Some(entry.local_open_label.clone()),
                    Some(entry.local_close_label.clone()),
                    collect_sources(
                        Some(entry.entry_id.clone()),
                        active_maintenance
                            .iter()
                            .map(|window| window.window_id.clone()),
                    ),
                )
            } else if !active_reset.is_empty() {
                (
                    CompiledSessionState::ResetBoundary,
                    active_reset[0].reason_code.clone(),
                    Some(entry.session_id.clone()),
                    Some(entry.trade_date.clone()),
                    entry.exchange_offset_minutes,
                    Some(entry.local_open_label.clone()),
                    Some(entry.local_close_label.clone()),
                    collect_sources(
                        Some(entry.entry_id.clone()),
                        active_reset.iter().map(|window| window.window_id.clone()),
                    ),
                )
            } else if !active_delivery.is_empty() {
                (
                    CompiledSessionState::DeliveryFence,
                    active_delivery[0].reason_code.clone(),
                    Some(entry.session_id.clone()),
                    Some(entry.trade_date.clone()),
                    entry.exchange_offset_minutes,
                    Some(entry.local_open_label.clone()),
                    Some(entry.local_close_label.clone()),
                    collect_sources(
                        Some(entry.entry_id.clone()),
                        active_delivery
                            .iter()
                            .map(|window| window.window_id.clone()),
                    ),
                )
            } else if !active_policy.is_empty() {
                (
                    CompiledSessionState::PolicyRestricted,
                    active_policy[0].reason_code.clone(),
                    Some(entry.session_id.clone()),
                    Some(entry.trade_date.clone()),
                    entry.exchange_offset_minutes,
                    Some(entry.local_open_label.clone()),
                    Some(entry.local_close_label.clone()),
                    collect_sources(
                        Some(entry.entry_id.clone()),
                        active_policy.iter().map(|window| window.window_id.clone()),
                    ),
                )
            } else {
                (
                    CompiledSessionState::Tradeable,
                    if entry.kind == SessionDayKind::EarlyClose {
                        "EARLY_CLOSE_SESSION_TRADEABLE".to_string()
                    } else {
                        "SESSION_OPEN_TRADEABLE".to_string()
                    },
                    Some(entry.session_id.clone()),
                    Some(entry.trade_date.clone()),
                    entry.exchange_offset_minutes,
                    Some(entry.local_open_label.clone()),
                    Some(entry.local_close_label.clone()),
                    vec![entry.entry_id.clone()],
                )
            }
        } else if !active_maintenance.is_empty() {
            (
                CompiledSessionState::Maintenance,
                active_maintenance[0].reason_code.clone(),
                None,
                None,
                0,
                None,
                None,
                collect_sources(
                    None,
                    active_maintenance
                        .iter()
                        .map(|window| window.window_id.clone()),
                ),
            )
        } else if !active_reset.is_empty() {
            (
                CompiledSessionState::ResetBoundary,
                active_reset[0].reason_code.clone(),
                None,
                None,
                0,
                None,
                None,
                collect_sources(
                    None,
                    active_reset.iter().map(|window| window.window_id.clone()),
                ),
            )
        } else if !active_delivery.is_empty() {
            (
                CompiledSessionState::DeliveryFence,
                active_delivery[0].reason_code.clone(),
                None,
                None,
                0,
                None,
                None,
                collect_sources(
                    None,
                    active_delivery
                        .iter()
                        .map(|window| window.window_id.clone()),
                ),
            )
        } else if !active_policy.is_empty() {
            (
                CompiledSessionState::PolicyRestricted,
                active_policy[0].reason_code.clone(),
                None,
                None,
                0,
                None,
                None,
                collect_sources(
                    None,
                    active_policy.iter().map(|window| window.window_id.clone()),
                ),
            )
        } else {
            let (
                reason_code,
                source_ids,
                exchange_offset_minutes,
                local_open_label,
                local_close_label,
            ) = closed_gap_context(&entries, &start_utc);
            (
                CompiledSessionState::Closed,
                reason_code,
                None,
                None,
                exchange_offset_minutes,
                local_open_label,
                local_close_label,
                source_ids,
            )
        };

        raw_slices.push(CompiledSessionSlice {
            slice_id: format!("{}:slice:{index:03}", request.artifact_id),
            session_id,
            trade_date,
            start_utc,
            end_utc,
            state,
            reason_code,
            source_ids,
            exchange_offset_minutes,
            local_open_label,
            local_close_label,
        });
    }

    let slices = merge_adjacent_slices(raw_slices, &request.artifact_id);
    Ok(CompiledSessionArtifact {
        artifact_id: request.artifact_id.clone(),
        retained_artifact_id: format!("runtime_state/schedules/{}.json", request.artifact_id),
        product_profile_id: request.product_profile_id,
        symbol: request.symbol,
        calendar_id: request.calendar_id,
        exchange_timezone: request.exchange_timezone,
        exchange_calendar_source: request.exchange_calendar_source,
        event_window_source: request.event_window_source,
        maintenance_window_ids: request.maintenance_window_ids,
        delivery_fence_rule: request.delivery_fence_rule,
        delivery_fence_input: request.delivery_fence_input,
        generated_at_utc: request.generated_at_utc,
        compiled_from_utc,
        compiled_to_utc,
        slices,
    })
}

fn collect_sources(entry_id: Option<String>, iter: impl Iterator<Item = String>) -> Vec<String> {
    let mut ordered = BTreeSet::new();
    if let Some(entry_id) = entry_id {
        ordered.insert(entry_id);
    }
    for value in iter {
        ordered.insert(value);
    }
    ordered.into_iter().collect()
}

fn closed_gap_context(
    entries: &[SessionCalendarEntry],
    start_utc: &str,
) -> (String, Vec<String>, i16, Option<String>, Option<String>) {
    if let Some(previous) = entries
        .iter()
        .filter(|entry| entry.close_utc.as_str() <= start_utc)
        .max_by(|left, right| left.close_utc.cmp(&right.close_utc))
    {
        if previous.kind == SessionDayKind::EarlyClose {
            return (
                "EARLY_CLOSE_SESSION_ENDED".to_string(),
                vec![previous.entry_id.clone()],
                previous.exchange_offset_minutes,
                Some(previous.local_open_label.clone()),
                Some(previous.local_close_label.clone()),
            );
        }
    }
    (
        "BETWEEN_COMPILED_SESSIONS".to_string(),
        Vec::new(),
        0,
        None,
        None,
    )
}

fn merge_adjacent_slices(
    slices: Vec<CompiledSessionSlice>,
    artifact_id: &str,
) -> Vec<CompiledSessionSlice> {
    let mut merged: Vec<CompiledSessionSlice> = Vec::new();
    for slice in slices {
        if let Some(previous) = merged.last_mut() {
            if previous.end_utc == slice.start_utc
                && previous.session_id == slice.session_id
                && previous.trade_date == slice.trade_date
                && previous.state == slice.state
                && previous.reason_code == slice.reason_code
                && previous.source_ids == slice.source_ids
                && previous.exchange_offset_minutes == slice.exchange_offset_minutes
                && previous.local_open_label == slice.local_open_label
                && previous.local_close_label == slice.local_close_label
            {
                previous.end_utc = slice.end_utc;
                continue;
            }
        }
        merged.push(slice);
    }

    for (index, slice) in merged.iter_mut().enumerate() {
        slice.slice_id = format!("{artifact_id}:slice:{index:03}");
    }
    merged
}

fn validate_interval(
    label: &'static str,
    start_utc: &str,
    end_utc: &str,
) -> Result<(), ScheduleError> {
    if start_utc >= end_utc {
        return Err(ScheduleError::InvertedWindow {
            label,
            start_utc: start_utc.to_string(),
            end_utc: end_utc.to_string(),
        });
    }
    Ok(())
}

fn validate_utc_timestamp(field: &'static str, value: &str) -> Result<(), ScheduleError> {
    let bytes = value.as_bytes();
    let valid = bytes.len() == 20
        && bytes[4] == b'-'
        && bytes[7] == b'-'
        && bytes[10] == b'T'
        && bytes[13] == b':'
        && bytes[16] == b':'
        && bytes[19] == b'Z'
        && bytes.iter().enumerate().all(|(index, byte)| {
            matches!(index, 4 | 7 | 10 | 13 | 16 | 19) || byte.is_ascii_digit()
        });
    if valid {
        Ok(())
    } else {
        Err(ScheduleError::InvalidTimestamp {
            field,
            value: value.to_string(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::{
        CompiledSessionState, DeliveryFenceWindowDefinition, MaintenanceWindowDefinition,
        PolicyOverlayWindowDefinition, ScheduleCompileRequest, ScheduleError, SessionCalendarEntry,
        SessionDayKind, compile_schedule,
    };

    fn sample_request() -> ScheduleCompileRequest {
        ScheduleCompileRequest::new(
            "compiled_schedule_gold_reset_v1",
            "oneoz_comex_v1",
            "1OZ",
            "comex_metals_globex_v1",
            "America/Chicago",
            "compiled_exchange_calendars",
            "resolved_context_bundles",
            vec!["daily_16:00_to_17:00_ct".to_string()],
            "block_tradeability_when_delivery_window_is_active",
            "delivery_window_status",
            "2026-03-15T12:00:00Z",
            vec![
                SessionCalendarEntry::new(
                    "winter-2026-02-18",
                    "globex_2026_02_18",
                    "2026-02-18",
                    "comex_metals_globex_v1",
                    "2026-02-17T23:00:00Z",
                    "2026-02-18T22:00:00Z",
                    SessionDayKind::Regular,
                    -360,
                    "17:00 CT",
                    "16:00 CT",
                ),
                SessionCalendarEntry::new(
                    "summer-2026-03-17",
                    "globex_2026_03_17",
                    "2026-03-17",
                    "comex_metals_globex_v1",
                    "2026-03-16T22:00:00Z",
                    "2026-03-17T21:00:00Z",
                    SessionDayKind::Regular,
                    -300,
                    "17:00 CT",
                    "16:00 CT",
                ),
                SessionCalendarEntry::new(
                    "summer-2026-03-18",
                    "globex_2026_03_18",
                    "2026-03-18",
                    "comex_metals_globex_v1",
                    "2026-03-17T22:00:00Z",
                    "2026-03-18T21:00:00Z",
                    SessionDayKind::Regular,
                    -300,
                    "17:00 CT",
                    "16:00 CT",
                ),
            ],
            vec![MaintenanceWindowDefinition::new(
                "maintenance-2026-03-17",
                "daily_16:00_to_17:00_ct",
                "2026-03-17T21:00:00Z",
                "2026-03-17T22:00:00Z",
                "DAILY_MAINTENANCE_WINDOW",
            )],
            vec![DeliveryFenceWindowDefinition::new(
                "delivery-2026-03-18",
                "block_tradeability_when_delivery_window_is_active",
                "delivery_window_status",
                "2026-03-18T13:00:00Z",
                "2026-03-18T14:00:00Z",
                "DELIVERY_FENCE_ACTIVE",
            )],
            vec![PolicyOverlayWindowDefinition::new(
                "reset-2026-03-17",
                "resolved_context_bundles",
                "2026-03-17T22:00:00Z",
                "2026-03-17T22:05:00Z",
                CompiledSessionState::ResetBoundary,
                "SESSION_RESET_RECONNECT_WINDOW",
            )],
        )
    }

    #[test]
    fn compiler_retains_dst_shift_and_policy_sources() {
        let artifact = compile_schedule(sample_request()).expect("schedule should compile");
        let winter = artifact
            .evaluate_at("2026-02-18T00:00:00Z")
            .expect("winter session should evaluate");
        let summer = artifact
            .evaluate_at("2026-03-18T15:00:00Z")
            .expect("summer session should evaluate");

        assert_eq!(
            "compiled_exchange_calendars",
            artifact.exchange_calendar_source
        );
        assert_eq!("resolved_context_bundles", artifact.event_window_source);
        assert_eq!(-360, winter.exchange_offset_minutes);
        assert_eq!(-300, summer.exchange_offset_minutes);
        assert_eq!("tradeable", winter.state.as_str());
        assert_eq!("tradeable", summer.state.as_str());
    }

    #[test]
    fn compiler_marks_maintenance_reset_and_delivery_fence_windows() {
        let artifact = compile_schedule(sample_request()).expect("schedule should compile");

        let maintenance = artifact
            .evaluate_at("2026-03-17T21:15:00Z")
            .expect("maintenance window should evaluate");
        let reset = artifact
            .evaluate_at("2026-03-17T22:02:00Z")
            .expect("reset boundary should evaluate");
        let delivery = artifact
            .evaluate_at("2026-03-18T13:30:00Z")
            .expect("delivery fence should evaluate");

        assert_eq!(CompiledSessionState::Maintenance, maintenance.state);
        assert_eq!("DAILY_MAINTENANCE_WINDOW", maintenance.reason_code);
        assert_eq!(CompiledSessionState::ResetBoundary, reset.state);
        assert_eq!("SESSION_RESET_RECONNECT_WINDOW", reset.reason_code);
        assert_eq!(CompiledSessionState::DeliveryFence, delivery.state);
        assert_eq!("DELIVERY_FENCE_ACTIVE", delivery.reason_code);
    }

    #[test]
    fn compiler_covers_holiday_closure_and_early_close_gaps() {
        let request = ScheduleCompileRequest::new(
            "holiday_and_early_close",
            "oneoz_comex_v1",
            "1OZ",
            "comex_metals_globex_v1",
            "America/Chicago",
            "compiled_exchange_calendars",
            "resolved_context_bundles",
            vec!["daily_16:00_to_17:00_ct".to_string()],
            "block_tradeability_when_delivery_window_is_active",
            "delivery_window_status",
            "2026-07-01T12:00:00Z",
            vec![
                SessionCalendarEntry::new(
                    "early-close-2026-07-03",
                    "globex_2026_07_03",
                    "2026-07-03",
                    "comex_metals_globex_v1",
                    "2026-07-02T22:00:00Z",
                    "2026-07-03T17:00:00Z",
                    SessionDayKind::EarlyClose,
                    -300,
                    "17:00 CT",
                    "12:00 CT",
                ),
                SessionCalendarEntry::new(
                    "holiday-2026-12-25",
                    "globex_2026_12_25",
                    "2026-12-25",
                    "comex_metals_globex_v1",
                    "2026-12-24T23:00:00Z",
                    "2026-12-25T22:00:00Z",
                    SessionDayKind::HolidayClosure,
                    -360,
                    "17:00 CT",
                    "16:00 CT",
                ),
            ],
            Vec::new(),
            Vec::new(),
            Vec::new(),
        );
        let artifact = compile_schedule(request).expect("schedule should compile");

        let early_close = artifact
            .evaluate_at("2026-07-03T16:00:00Z")
            .expect("early close session should still be tradeable before close");
        let after_close = artifact
            .evaluate_at("2026-07-03T18:00:00Z")
            .expect("gap after early close should remain inspectable");
        let holiday = artifact
            .evaluate_at("2026-12-25T15:00:00Z")
            .expect("holiday closure should evaluate");

        assert_eq!(CompiledSessionState::Tradeable, early_close.state);
        assert_eq!("EARLY_CLOSE_SESSION_TRADEABLE", early_close.reason_code);
        assert_eq!(CompiledSessionState::Closed, after_close.state);
        assert_eq!("EARLY_CLOSE_SESSION_ENDED", after_close.reason_code);
        assert_eq!(CompiledSessionState::HolidayClosure, holiday.state);
        assert_eq!("HOLIDAY_EXCHANGE_CLOSED", holiday.reason_code);
    }

    #[test]
    fn compiler_rejects_unapproved_or_mismatched_inputs() {
        let mut request = sample_request();
        request.maintenance_windows[0].policy_window_id = "unknown_window".to_string();
        let error = compile_schedule(request).expect_err("unknown maintenance window should fail");
        assert_eq!(
            ScheduleError::UnapprovedMaintenanceWindow {
                window_id: "maintenance-2026-03-17".to_string(),
                policy_window_id: "unknown_window".to_string(),
            },
            error
        );
    }
}
