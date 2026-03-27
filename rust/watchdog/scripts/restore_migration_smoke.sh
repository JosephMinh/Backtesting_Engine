#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export CARGO_TARGET_DIR="$repo_root/target"
export TMPDIR="$repo_root/target/tmp"
mkdir -p "$TMPDIR"

artifact_root="${1:-${TMPDIR:-/tmp}/backtesting_engine_watchdog_restore_migration_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$artifact_root"

cargo run -p backtesting-engine-watchdog -- \
  restore-drill happy-path \
  --artifact-dir "$artifact_root/restore-safe-resume"

cargo run -p backtesting-engine-watchdog -- \
  restore-drill ambiguous-state \
  --artifact-dir "$artifact_root/restore-safe-halt"

cargo run -p backtesting-engine-watchdog -- \
  execute-migration incremental-upgrade \
  --artifact-dir "$artifact_root/migration-executed"

printf 'artifact_root=%s\n' "$artifact_root"
