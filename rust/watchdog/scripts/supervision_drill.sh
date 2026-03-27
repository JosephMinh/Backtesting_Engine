#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export CARGO_TARGET_DIR="$repo_root/target"
export TMPDIR="$repo_root/target/tmp"
mkdir -p "$TMPDIR"

artifact_root="${1:-$repo_root/target/tmp/backtesting_engine_watchdog_supervision_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$artifact_root"

cargo run -p backtesting-engine-watchdog -- \
  supervision-drill opsd-restart-into-recovering \
  --artifact-dir "$artifact_root/opsd-restart-into-recovering"

cargo run -p backtesting-engine-watchdog -- \
  supervision-drill broker-gateway-restart-loop \
  --artifact-dir "$artifact_root/broker-gateway-restart-loop"

printf 'artifact_root=%s\n' "$artifact_root"
