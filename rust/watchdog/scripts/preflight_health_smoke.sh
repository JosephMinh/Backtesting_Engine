#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export CARGO_TARGET_DIR="$repo_root/target"
export TMPDIR="$repo_root/target/tmp"
mkdir -p "$TMPDIR"

artifact_root="${1:-${TMPDIR:-/tmp}/backtesting_engine_watchdog_preflight_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$artifact_root"

cargo run -p backtesting-engine-watchdog -- \
  clock-health green \
  --artifact-dir "$artifact_root/clock-green"

cargo run -p backtesting-engine-watchdog -- \
  secret-health break-glass-review-required \
  --artifact-dir "$artifact_root/secret-blocked"

cargo run -p backtesting-engine-watchdog -- \
  activation-preflight blocked-clock \
  --artifact-dir "$artifact_root/preflight-blocked"

cargo run -p backtesting-engine-watchdog -- \
  activation-preflight green \
  --artifact-dir "$artifact_root/preflight-green"

printf 'artifact_root=%s\n' "$artifact_root"
