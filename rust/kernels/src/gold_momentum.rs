use std::collections::VecDeque;

use crate::{
    BarInput, KernelArtifactBinding, KernelBindingError, KernelIdentity, SignalDecision,
    SignalDisposition, SignalKernel,
};

pub const GOLD_MOMENTUM_SIGNAL_NAME: &str = "gold_momentum";
pub const GOLD_MOMENTUM_BINDING_MODULE: &str = "python.bindings._kernels.gold_momentum";
pub const GOLD_MOMENTUM_IDENTITY: KernelIdentity = KernelIdentity {
    strategy_family_id: GOLD_MOMENTUM_SIGNAL_NAME,
    rust_crate: "rust/kernels",
    python_binding_module: GOLD_MOMENTUM_BINDING_MODULE,
    kernel_abi_version: "abi_v2",
    state_serialization_version: "state_v2",
    semantic_version: "1.2.0",
};

/// Snapshot encoding drift for the canonical gold-momentum kernel.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SnapshotDecodeError {
    InvalidFormat,
    UnsupportedStrategyFamily(String),
    UnsupportedAbiVersion(String),
    UnsupportedStateVersion(String),
    InvalidLookback,
    InvalidThreshold,
    InvalidSequence,
    InvalidClose(String),
}

/// Serialized state retained for replay handoff and incremental warm restart.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct GoldMomentumSnapshot {
    pub strategy_family_id: String,
    pub kernel_abi_version: String,
    pub state_serialization_version: String,
    pub lookback_bars: usize,
    pub threshold_ticks: i64,
    pub last_sequence_number: u64,
    pub recent_closes: Vec<i64>,
}

impl GoldMomentumSnapshot {
    pub fn encode(&self) -> String {
        let closes = self
            .recent_closes
            .iter()
            .map(i64::to_string)
            .collect::<Vec<_>>()
            .join(",");
        format!(
            "{}|{}|{}|{}|{}|{}|{}",
            self.strategy_family_id,
            self.kernel_abi_version,
            self.state_serialization_version,
            self.lookback_bars,
            self.threshold_ticks,
            self.last_sequence_number,
            closes,
        )
    }

    pub fn decode(encoded: &str) -> Result<Self, SnapshotDecodeError> {
        let mut parts = encoded.split('|');
        let Some(strategy_family_id) = parts.next() else {
            return Err(SnapshotDecodeError::InvalidFormat);
        };
        let Some(kernel_abi_version) = parts.next() else {
            return Err(SnapshotDecodeError::InvalidFormat);
        };
        let Some(state_serialization_version) = parts.next() else {
            return Err(SnapshotDecodeError::InvalidFormat);
        };
        let Some(lookback_bars) = parts.next() else {
            return Err(SnapshotDecodeError::InvalidFormat);
        };
        let Some(threshold_ticks) = parts.next() else {
            return Err(SnapshotDecodeError::InvalidFormat);
        };
        let Some(last_sequence_number) = parts.next() else {
            return Err(SnapshotDecodeError::InvalidFormat);
        };
        let Some(recent_closes) = parts.next() else {
            return Err(SnapshotDecodeError::InvalidFormat);
        };
        if parts.next().is_some() {
            return Err(SnapshotDecodeError::InvalidFormat);
        }

        let lookback_bars = lookback_bars
            .parse::<usize>()
            .map_err(|_| SnapshotDecodeError::InvalidLookback)?;
        let threshold_ticks = threshold_ticks
            .parse::<i64>()
            .map_err(|_| SnapshotDecodeError::InvalidThreshold)?;
        let last_sequence_number = last_sequence_number
            .parse::<u64>()
            .map_err(|_| SnapshotDecodeError::InvalidSequence)?;
        let recent_closes = if recent_closes.is_empty() {
            Vec::new()
        } else {
            recent_closes
                .split(',')
                .map(|value| {
                    value
                        .parse::<i64>()
                        .map_err(|_| SnapshotDecodeError::InvalidClose(value.to_owned()))
                })
                .collect::<Result<Vec<_>, _>>()?
        };

        Ok(Self {
            strategy_family_id: strategy_family_id.to_owned(),
            kernel_abi_version: kernel_abi_version.to_owned(),
            state_serialization_version: state_serialization_version.to_owned(),
            lookback_bars,
            threshold_ticks,
            last_sequence_number,
            recent_closes,
        })
    }
}

/// Deterministic canonical momentum kernel used by promotable/live-eligible families.
#[derive(Clone, Debug)]
pub struct GoldMomentumKernel {
    lookback_bars: usize,
    threshold_ticks: i64,
    recent_closes: VecDeque<i64>,
    last_sequence_number: u64,
}

impl GoldMomentumKernel {
    pub fn new(lookback_bars: usize, threshold_ticks: i64) -> Self {
        assert!(lookback_bars > 0, "lookback_bars must be positive");
        assert!(threshold_ticks >= 0, "threshold_ticks must be non-negative");
        Self {
            lookback_bars,
            threshold_ticks,
            recent_closes: VecDeque::with_capacity(lookback_bars + 1),
            last_sequence_number: 0,
        }
    }

    pub fn lookback_bars(&self) -> usize {
        self.lookback_bars
    }

    pub fn threshold_ticks(&self) -> i64 {
        self.threshold_ticks
    }

    pub fn snapshot(&self) -> GoldMomentumSnapshot {
        GoldMomentumSnapshot {
            strategy_family_id: GOLD_MOMENTUM_IDENTITY.strategy_family_id.to_owned(),
            kernel_abi_version: GOLD_MOMENTUM_IDENTITY.kernel_abi_version.to_owned(),
            state_serialization_version: GOLD_MOMENTUM_IDENTITY
                .state_serialization_version
                .to_owned(),
            lookback_bars: self.lookback_bars,
            threshold_ticks: self.threshold_ticks,
            last_sequence_number: self.last_sequence_number,
            recent_closes: self.recent_closes.iter().copied().collect(),
        }
    }

    pub fn from_snapshot(snapshot: GoldMomentumSnapshot) -> Result<Self, SnapshotDecodeError> {
        if snapshot.strategy_family_id != GOLD_MOMENTUM_IDENTITY.strategy_family_id {
            return Err(SnapshotDecodeError::UnsupportedStrategyFamily(
                snapshot.strategy_family_id,
            ));
        }
        if snapshot.kernel_abi_version != GOLD_MOMENTUM_IDENTITY.kernel_abi_version {
            return Err(SnapshotDecodeError::UnsupportedAbiVersion(
                snapshot.kernel_abi_version,
            ));
        }
        if snapshot.state_serialization_version
            != GOLD_MOMENTUM_IDENTITY.state_serialization_version
        {
            return Err(SnapshotDecodeError::UnsupportedStateVersion(
                snapshot.state_serialization_version,
            ));
        }
        if snapshot.lookback_bars == 0 {
            return Err(SnapshotDecodeError::InvalidLookback);
        }
        if snapshot.recent_closes.len() > snapshot.lookback_bars + 1 {
            return Err(SnapshotDecodeError::InvalidFormat);
        }

        Ok(Self {
            lookback_bars: snapshot.lookback_bars,
            threshold_ticks: snapshot.threshold_ticks,
            recent_closes: snapshot.recent_closes.into_iter().collect(),
            last_sequence_number: snapshot.last_sequence_number,
        })
    }

    pub fn from_encoded_snapshot(encoded: &str) -> Result<Self, SnapshotDecodeError> {
        Self::from_snapshot(GoldMomentumSnapshot::decode(encoded)?)
    }

    pub fn binding(
        candidate_bundle: impl Into<String>,
        resolved_context_bundle: impl Into<String>,
        signal_kernel: impl Into<String>,
    ) -> Result<KernelArtifactBinding, KernelBindingError> {
        KernelArtifactBinding::new(
            GOLD_MOMENTUM_IDENTITY,
            candidate_bundle,
            resolved_context_bundle,
            signal_kernel,
        )
    }

    pub fn evaluate_series(
        lookback_bars: usize,
        threshold_ticks: i64,
        inputs: &[BarInput],
    ) -> Vec<SignalDecision> {
        let mut kernel = Self::new(lookback_bars, threshold_ticks);
        let mut decisions = Vec::new();
        for input in inputs {
            if let Some(decision) = kernel.evaluate_bar(*input) {
                decisions.push(decision);
            }
        }
        decisions
    }

    fn score_ticks(&self) -> Option<i64> {
        if self.recent_closes.len() < self.lookback_bars + 1 {
            return None;
        }
        let oldest = self.recent_closes.front().copied()?;
        let newest = self.recent_closes.back().copied()?;
        Some(newest - oldest)
    }
}

impl SignalKernel for GoldMomentumKernel {
    fn identity(&self) -> KernelIdentity {
        GOLD_MOMENTUM_IDENTITY
    }

    fn warmup_bars(&self) -> usize {
        self.lookback_bars
    }

    fn evaluate_bar(&mut self, input: BarInput) -> Option<SignalDecision> {
        self.recent_closes.push_back(input.close_ticks);
        if self.recent_closes.len() > self.lookback_bars + 1 {
            self.recent_closes.pop_front();
        }
        self.last_sequence_number = input.sequence_number;
        let score_ticks = self.score_ticks()?;
        let disposition = if score_ticks >= self.threshold_ticks {
            SignalDisposition::Long
        } else if score_ticks <= -self.threshold_ticks {
            SignalDisposition::Short
        } else {
            SignalDisposition::Flat
        };
        Some(SignalDecision {
            sequence_number: input.sequence_number,
            signal_name: GOLD_MOMENTUM_SIGNAL_NAME,
            score_ticks,
            disposition,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::{
        GOLD_MOMENTUM_IDENTITY, GoldMomentumKernel, GoldMomentumSnapshot, SnapshotDecodeError,
    };
    use crate::{BarInput, SignalDisposition, SignalKernel};

    fn golden_series() -> Vec<BarInput> {
        [100, 104, 108, 112, 109, 116, 105]
            .into_iter()
            .enumerate()
            .map(|(index, close_ticks)| BarInput {
                sequence_number: (index + 1) as u64,
                close_ticks,
            })
            .collect()
    }

    fn lcg_series(seed: u64, len: usize) -> Vec<BarInput> {
        let mut state = seed;
        let mut close_ticks = 10_000_i64 + (seed as i64 % 17);
        let mut series = Vec::with_capacity(len);
        for sequence_number in 1..=len {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            let delta = ((state >> 32) as i64).rem_euclid(11) - 5;
            close_ticks = (close_ticks + delta).max(1);
            series.push(BarInput {
                sequence_number: sequence_number as u64,
                close_ticks,
            });
        }
        series
    }

    #[test]
    fn golden_series_emits_expected_decisions() {
        let decisions = GoldMomentumKernel::evaluate_series(3, 6, &golden_series());
        let actual = decisions
            .iter()
            .map(|decision| {
                (
                    decision.sequence_number,
                    decision.disposition,
                    decision.score_ticks,
                )
            })
            .collect::<Vec<_>>();
        assert_eq!(
            vec![
                (4, SignalDisposition::Long, 12),
                (5, SignalDisposition::Flat, 5),
                (6, SignalDisposition::Long, 8),
                (7, SignalDisposition::Short, -7),
            ],
            actual
        );
    }

    #[test]
    fn snapshot_round_trip_preserves_state() {
        let mut kernel = GoldMomentumKernel::new(3, 6);
        for input in golden_series().into_iter().take(5) {
            let _ = kernel.evaluate_bar(input);
        }
        let encoded = kernel.snapshot().encode();
        let restored = GoldMomentumKernel::from_encoded_snapshot(&encoded)
            .expect("snapshot should round-trip");
        assert_eq!(kernel.snapshot(), restored.snapshot());
    }

    #[test]
    fn snapshot_decode_rejects_abi_or_state_drift() {
        let snapshot = GoldMomentumSnapshot {
            strategy_family_id: GOLD_MOMENTUM_IDENTITY.strategy_family_id.to_owned(),
            kernel_abi_version: "abi_v999".to_owned(),
            state_serialization_version: GOLD_MOMENTUM_IDENTITY
                .state_serialization_version
                .to_owned(),
            lookback_bars: 3,
            threshold_ticks: 6,
            last_sequence_number: 4,
            recent_closes: vec![100, 104, 108, 112],
        };
        let err =
            GoldMomentumKernel::from_snapshot(snapshot).expect_err("abi drift must be rejected");
        assert_eq!(
            SnapshotDecodeError::UnsupportedAbiVersion("abi_v999".to_owned()),
            err
        );

        let err = GoldMomentumKernel::from_encoded_snapshot("garbled")
            .expect_err("garbled snapshots must be rejected");
        assert_eq!(SnapshotDecodeError::InvalidFormat, err);
    }

    #[test]
    fn property_split_stream_restore_matches_continuous_execution() {
        for seed in 1_u64..=32 {
            let series = lcg_series(seed, 24);
            let continuous = GoldMomentumKernel::evaluate_series(4, 7, &series);

            let mut split_kernel = GoldMomentumKernel::new(4, 7);
            let mut split_decisions = Vec::new();
            for input in series.iter().copied().take(11) {
                if let Some(decision) = split_kernel.evaluate_bar(input) {
                    split_decisions.push(decision);
                }
            }
            let snapshot = split_kernel.snapshot().encode();
            let mut restored = GoldMomentumKernel::from_encoded_snapshot(&snapshot)
                .expect("snapshot should restore");
            for input in series.iter().copied().skip(11) {
                if let Some(decision) = restored.evaluate_bar(input) {
                    split_decisions.push(decision);
                }
            }

            assert_eq!(continuous, split_decisions, "seed {seed} diverged");
        }
    }

    #[test]
    fn bindings_attach_candidate_replay_and_signal_kernel_artifacts() {
        let binding = GoldMomentumKernel::binding(
            "candidate_bundles/gold_momentum_candidate_bundle_v1.json",
            "resolved_context_bundles/gold_momentum_context_v1.json",
            "signal_kernels/gold_momentum_v1.bin",
        )
        .expect("binding should validate");
        assert_eq!(
            GOLD_MOMENTUM_IDENTITY.canonical_digest(),
            binding.identity.canonical_digest()
        );
        assert_eq!("candidate_bundles", binding.candidate_bundle.root());
        assert_eq!("signal_kernels", binding.signal_kernel.root());
    }
}
