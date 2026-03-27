#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CARGO_TARGET_DIR="$repo_root/target/runtime-stack-smoke/cargo-target"
export TMPDIR="$repo_root/target/runtime-stack-smoke/tmp"
mkdir -p "$CARGO_TARGET_DIR" "$TMPDIR"

artifact_root="${1:-$repo_root/target/runtime-stack-smoke/artifacts/bringup_$(date +%Y%m%dT%H%M%S)}"

mkdir -p "$artifact_root"

python3 -m infra.runtime_stack smoke --artifact-dir "$artifact_root"

printf 'artifact_root=%s\n' "$artifact_root"
