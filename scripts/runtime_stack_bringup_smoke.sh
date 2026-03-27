#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CARGO_TARGET_DIR="$repo_root/target/runtime-stack-smoke/cargo-target"
export TMPDIR="$repo_root/target/runtime-stack-smoke/tmp"
mkdir -p "$CARGO_TARGET_DIR" "$TMPDIR"

artifact_parent="$repo_root/target/runtime-stack-smoke/artifacts"
mkdir -p "$artifact_parent"
if [[ $# -ge 1 ]]; then
  artifact_root="$1"
  mkdir -p "$artifact_root"
else
  artifact_root="$(mktemp -d "$artifact_parent/bringup_XXXXXX")"
fi

python3 -m infra.runtime_stack smoke --artifact-dir "$artifact_root"

printf 'artifact_root=%s\n' "$artifact_root"
