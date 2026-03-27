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
  artifact_root="$(mktemp -d "$artifact_parent/backtesting_engine_guardian_drill_XXXXXX")"
fi

cargo run -p backtesting-engine-guardian -- \
  emergency-drill authorized-flatten \
  --artifact-dir "$artifact_root/authorized-flatten"

cargo run -p backtesting-engine-guardian -- \
  emergency-drill impaired-connectivity \
  --artifact-dir "$artifact_root/impaired-connectivity"

printf 'artifact_root=%s\n' "$artifact_root"
