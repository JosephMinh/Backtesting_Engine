#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export CARGO_TARGET_DIR="$repo_root/target"
export TMPDIR="$repo_root/target/tmp"
mkdir -p "$TMPDIR"

artifact_parent="$repo_root/target/tmp"
if [[ $# -ge 1 ]]; then
  artifact_root="$1"
  mkdir -p "$artifact_root"
else
  artifact_root="$(mktemp -d "$artifact_parent/backtesting_engine_watchdog_supervision_XXXXXX")"
fi

cargo run -p backtesting-engine-watchdog -- \
  supervision-drill opsd-restart-into-recovering \
  --artifact-dir "$artifact_root/opsd-restart-into-recovering"

cargo run -p backtesting-engine-watchdog -- \
  supervision-drill broker-gateway-restart-loop \
  --artifact-dir "$artifact_root/broker-gateway-restart-loop"

printf 'artifact_root=%s\n' "$artifact_root"
