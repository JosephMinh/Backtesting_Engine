#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export CARGO_TARGET_DIR="$repo_root/target"
export TMPDIR="$repo_root/target/tmp"
mkdir -p "$TMPDIR"

artifact_parent="${TMPDIR:-/tmp}"
if [[ $# -ge 1 ]]; then
  artifact_root="$1"
  mkdir -p "$artifact_root"
else
  artifact_root="$(mktemp -d "$artifact_parent/backtesting_engine_watchdog_preflight_XXXXXX")"
fi

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
