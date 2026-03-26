# AGENTS.md - Backtesting_Engine

> Guidelines for AI coding agents working in this repository.

---

## Canonical Project Path

The canonical path for this repository is:

`/home/ubuntu/ntm_Dev/Backtesting_Engine`

Use that exact path for:

- agent registration
- tmux pane working directories
- MCP Agent Mail `project_key` / `human_key`
- absolute file references in notes, prompts, and docs

---

## RULE 0 - THE FUNDAMENTAL OVERRIDE PREROGATIVE

If the user gives a direct instruction, follow the user's instruction even if it conflicts with the defaults below.

---

## RULE NUMBER 1: NO FILE DELETION

**YOU ARE NEVER ALLOWED TO DELETE A FILE OR DIRECTORY WITHOUT EXPRESS PERMISSION.**

This includes:

- files you created yourself during the session
- temporary test files
- generated files
- "obsolete" files
- directories that appear empty

**YOU MUST ALWAYS ASK AND RECEIVE CLEAR, WRITTEN PERMISSION BEFORE EVER DELETING A FILE OR FOLDER OF ANY KIND.**

If a cleanup seems useful, propose it first. Do not execute it on your own.

---

## Irreversible Git & Filesystem Actions - DO NOT EVER BREAK GLASS

1. **Absolutely forbidden commands:** `git reset --hard`, `git clean -fd`, `rm -rf`, or any command that can delete or overwrite code or data must never be run unless the user explicitly provides the exact command and confirms they want the irreversible consequences.
2. **No guessing:** If there is any uncertainty about what a command might delete, overwrite, or detach from history, stop and ask.
3. **Safer alternatives first:** Prefer `git status`, `git diff`, backups, patch files, or non-destructive rollbacks before even considering destructive operations.
4. **Restate before execution:** If the user authorizes something destructive, restate the exact command, what it will affect, and wait for confirmation if anything is ambiguous.
5. **Document the action:** If a destructive command is ever run with permission, record the authorization text, the exact command, and the execution time in the final response.

---

## Public Disclosure and External Reports

Project planning notes and internal design documents are not automatically public-facing material.

- Do not quote or paste internal planning documents into public GitHub issues, PR descriptions, gists, pastebins, or external chats unless the user explicitly asks.
- For public bug reports, describe only the observable behavior, minimal repro, expected behavior, and relevant source locations.
- If a private document helps local reasoning, keep that reasoning local unless the user authorizes disclosure.

---

## Git Branch Policy

This repository currently uses `main`.

- Treat `main` as the default branch.
- Do not introduce `master` references in code, docs, scripts, or automation.
- If you find branch instructions that contradict the current repository state, flag them and fix them only with user approval.

---

## Read Order and Source of Truth

Before making substantial changes, read in this order:

1. `AGENTS.md`
2. `README.md` if present
3. `.claude/settings.toml` and `.ntm/policy.yaml` when relevant
4. The most relevant local design or planning document when needed for implementation details
5. Existing code and tests

When sources conflict, use this priority:

1. Latest direct user instruction
2. `AGENTS.md`
3. Repository code and tests
4. Other repository docs and planning notes

---

## Current Repository State

This repository is currently in an early-stage, scaffold-heavy state.

- Do not assume the final architecture is fully represented by the current file tree.
- Do not invent extra frameworks, services, or folder hierarchies casually.
- If key manifests are missing, avoid pretending the toolchain is settled.
- Prefer small, explicit structural steps over broad speculative scaffolding.

---

## Code Editing Discipline

### No Script-Based Rewrite Passes

**NEVER** run a script that mass-edits source files in this repo unless the user explicitly asks for that exact approach.

Brittle regex or codemod-style rewrites can silently corrupt code and docs.

- Make code changes manually.
- For many simple edits, work carefully in small batches.
- For subtle edits, read enough surrounding context to understand the implications before changing anything.

### No File Proliferation

Prefer revising existing files in place.

Do **not** create throwaway variants like:

- `main_v2.py`
- `engine_new.rs`
- `backtest_final_final.py`
- `notes_updated.md`

New files should be created only when they represent genuinely new functionality or clearly necessary new documentation.

### Respect Unrelated Changes

- Never revert unrelated user changes.
- If you see a dirty worktree, isolate your edits and work with the existing state.
- If another change conflicts directly with your task, stop and ask instead of bulldozing through it.
- Unexpected edits from other agents are normal in this environment and are not, by themselves, a reason to interrupt the user.
- Do not stash, revert, overwrite, or otherwise disturb work you did not create.
- Read the latest file contents carefully, adapt your change to the current state, and continue.
- If you absolutely must escalate, explain the exact blocking overlap, not merely that the worktree is dirty.

---

## Multi-Agent Worktree Behavior

This environment may have multiple agents touching the repository in parallel.

Treat the following as normal:

- files changing while you work
- new untracked files appearing
- timestamps moving unexpectedly
- diffs in areas you did not edit

Default behavior:

1. Assume concurrent changes are legitimate.
2. Re-read the current file before editing if it may have changed.
3. Merge your work with the current contents instead of trying to restore an older state.
4. Preserve others' changes unless the user explicitly instructs otherwise.

Do **not** do any of the following just because you noticed concurrent edits:

- `git stash`
- `git checkout -- <file>`
- `git restore`
- `git reset`
- manual deletion of "unexpected" files

Escalate only when:

- the same lines or same design surface are in direct conflict
- the current state makes the task ambiguous
- proceeding would likely destroy or invalidate someone else's work

When escalating, be specific:

- identify the exact file or files
- identify the exact conflict
- explain why it cannot be resolved locally

---

## Architecture Hygiene

- Prefer one canonical implementation of important business logic rather than duplicated logic across multiple languages or layers.
- Do not create compatibility shims or duplicate "old" and "new" paths unless the user explicitly wants that tradeoff.
- Keep interfaces explicit and versioned when behavior matters.
- Favor deterministic, testable behavior over clever shortcuts.

If the repo later grows into multiple language areas, keep the boundary between them clean and document shared contracts.

---

## Toolchain Policy

Use the toolchain that the repository actually declares.

- If a Python workspace is present, prefer the repository's declared workflow and lockfile. If there is no declared workflow yet, prefer `uv` over ad hoc environment management.
- If a Rust workspace is present, use `cargo`.
- If a JavaScript or TypeScript workspace is present, use the package manager implied by the lockfile.
- Do not introduce duplicate package managers or duplicate lockfiles.
- Do not add new infrastructure or dependencies casually just because the repo is young.

If the repository does not yet declare a toolchain for a component, ask before standardizing one if the choice would be hard to undo.

---

## Context Efficiency Tools

This environment includes both `context-mode` and `rtk`. Use them aggressively to reduce context waste.

### Preferred Order

1. Use `context-mode` MCP tools first when they are available.
2. Use `rtk` for shell-level filtering when running ordinary CLI commands directly.
3. Avoid dumping large raw command output into agent context unless there is a specific reason.

### context-mode

Use `context-mode` for any operation that would otherwise produce large output or require repeated shell reads.

Prefer these patterns:

- `ctx_batch_execute` for multiple file reads or repo inspection in one pass
- `ctx_execute` for commands likely to exceed a small screen of output
- `ctx_execute_file` for large files, logs, CSV, JSON, and other data files
- `ctx_fetch_and_index` or `ctx_index` plus `ctx_search` for documentation and reference material
- `ctx_stats` when checking whether context usage is staying efficient

Use cases:

- reading long docs without pasting them into context
- running test suites and retrieving only the relevant failures
- exploring repo structure without pulling every file listing into the transcript
- indexing external documentation and searching it on demand

### rtk

`rtk` is a CLI proxy that filters and summarizes command output before it reaches the model.

Prefer `rtk` wrappers instead of raw commands when using the shell directly for:

- `rtk read <file>` instead of dumping a long file with `cat`
- `rtk git diff`, `rtk git status`, `rtk diff`, `rtk log`
- `rtk test <command>` or `rtk err <command>` for noisy test and build commands
- `rtk find ...`, `rtk tree`, `rtk ls` for repo exploration
- `rtk json <command>` when the command returns large JSON
- `rtk deps`, `rtk grep`, `rtk summary`, `rtk cargo`, `rtk pytest`, `rtk mypy`, `rtk go`, `rtk golangci-lint` when applicable

### Practical Rule

If a command would normally produce more than about 20 lines of output, do not default to the raw command.

- Use `context-mode` if you want indexed, queryable results.
- Use `rtk` if you want a shell-native compact summary.

---

## Verification and Testing

After substantive code changes, you must verify the relevant surfaces.

Use the checks the repo actually supports. Typical examples:

- Python: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`
- Rust: `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo test`
- JavaScript or TypeScript: repo-defined lint, typecheck, and test commands

If the repo is too incomplete to run meaningful automated checks:

- say that explicitly
- run whatever narrow validation is still possible
- do not claim verification you did not perform

---

## Backwards Compatibility

This project is early enough that correctness and clarity matter more than preserving bad intermediate designs.

- Do not add compatibility wrappers by default.
- Do not keep dead patterns alive just because they already exist.
- Prefer clean replacements over layered hacks.

But:

- ask before removing files
- ask before removing public interfaces if the user has not said that breakage is acceptable

---

## Secrets, Credentials, and Trading-Sensitive Data

- Never commit secrets, tokens, broker credentials, or account identifiers.
- Never print secrets into logs, notes, or issue text.
- Treat operational credentials and account information as sensitive by default.
- If a bug can be reported without including sensitive values, do that.

---

## Third-Party Libraries and External APIs

If you are not certain how a library or external API should be used:

- consult the official documentation
- prefer current best practices
- avoid coding from vague memory when behavior is safety-critical or financially relevant

---

## Agent Mail and Multi-Agent Coordination

Use MCP Agent Mail when parallel work is happening.

Basic expectations:

1. Register with the canonical absolute project path.
2. Reserve files before editing shared surfaces.
3. Read your inbox and acknowledge messages that require acknowledgement.
4. Keep work in focused threads with clear subjects.

Useful operations:

- `ensure_project`
- `register_agent`
- `file_reservation_paths`
- `fetch_inbox`
- `acknowledge_message`
- `send_message`

---

## Beads / Issue Tracking

If the repository is using beads, treat it as the task system of record.

- Do not edit `.beads` files manually.
- Use `br ready` to find unblocked work.
- Mark work `in_progress` when starting.
- Close work with a reason when finishing.
- Run `br sync --flush-only` before commit when beads state changed.

Typical commands:

```bash
br ready --json
br update <id> --status in_progress --json
br close <id> --reason "Completed" --json
br sync --flush-only
```

---

## bv — Graph-Aware Triage Engine

If `bv` is installed for the workspace, use it to decide what to work on next.

**Scope boundary:** `bv` answers what is highest-value or most unblocking. `br` updates issue state. Agent Mail handles coordination and file reservations.

**CRITICAL:** Use only `--robot-*` flags for agent workflows. Bare `bv` launches an interactive TUI and can block your session.

Start here:

```bash
bv --robot-triage
bv --robot-next
```

High-value follow-ups:

```bash
bv --robot-plan
bv --robot-insights
bv --robot-alerts
bv --robot-suggest
bv --robot-graph --graph-format=mermaid
```

Useful scoping patterns:

```bash
bv --robot-plan --label backend
bv --robot-insights --as-of HEAD~30
bv --recipe actionable --robot-plan
bv --recipe high-impact --robot-triage
```

For lower context usage, prefer compact output when available:

```bash
bv --robot-triage --format toon
```

What to look for in `bv` output:

- top actionable work
- blockers that unlock downstream work
- stale or priority-misaligned issues
- cycles or dependency problems
- label or track bottlenecks

---

## UBS — Ultimate Bug Scanner

If `ubs` is installed, use it as a pre-commit or pre-handoff bug sweep after substantive code changes.

Golden rule:

- run `ubs` on the files you changed before concluding the work

Preferred usage:

```bash
ubs <changed-file-1> <changed-file-2>
ubs $(git diff --name-only --cached)
ubs --only=python,rust,golang .
```

How to use it correctly:

1. Read the finding carefully.
2. Inspect the referenced location and surrounding context.
3. Verify it is a real issue rather than blindly obeying the tool.
4. Fix the root cause.
5. Re-run `ubs` on the affected files.

Do not:

- ignore serious findings without inspection
- mass-apply speculative fixes
- claim the scan passed if you did not re-run it

---

## ast-grep vs ripgrep

Use `ast-grep` when structure matters. Use `rg` when plain text search is enough.

Prefer `ast-grep` or `sg` for:

- structured code search
- API migration work
- syntax-aware matching that should ignore comments and strings
- narrowly scoped, deliberate rewrites

Prefer `rg` for:

- locating strings, TODOs, logs, config keys, and filenames
- fast reconnaissance
- narrowing a search before deeper structural work

Rule of thumb:

- if correctness depends on syntax, use `ast-grep`
- if speed and broad text search matter, use `rg`

Important constraint:

- even though `ast-grep` can rewrite code, do not use it for broad automated repo rewrites unless the user explicitly wants that approach

Example patterns:

```bash
ast-grep run -p '$X.unwrap()'
rg -n 'TODO|FIXME' .
rg -l 'unsafe' . | xargs ast-grep run -p 'unsafe { $$$ }'
```

---

## Installed Tools Quick Reference

These tools are installed in this environment and should be used when appropriate.

| Command | Purpose |
|---------|---------|
| `ntm` | Session orchestration and agent workflows |
| `br` | Issue tracking and dependency-aware work management |
| `bv` | Graph-aware triage and prioritization |
| `ubs` | Bug scanning and static issue surfacing |
| `ast-grep` / `sg` | AST-aware structural search |
| `cass` | Search prior agent session history |
| `cm` | Procedural memory and context recall |
| `rtk` | Token-efficient CLI output filtering |
| `dcg` | Destructive Command Guard |
| `slb` | Two-person approval flow for dangerous commands |
| `tmux` | Session and pane navigation |

Safety-specific guidance:

- If `dcg` blocks a command, assume the block is intentional until you understand why.
- Do not bypass `dcg` or `slb` casually.
- If `slb` requires approval for a command, that is a sign the command is high-risk.

---

## Tmux Navigation

This environment uses `Ctrl-a` as the tmux prefix.

Useful keys:

| Keys | Action |
|------|--------|
| `Ctrl-a n` | Next window |
| `Ctrl-a p` | Previous window |
| `Ctrl-a 0-9` | Switch to window by number |
| `Ctrl-a h/j/k/l` | Move between panes |
| `Ctrl-a z` | Zoom or unzoom the current pane |
| `Ctrl-a d` | Detach from the session |

Do not assume the default tmux prefix is `Ctrl-b` here.

---

## Documentation Discipline

- Keep documentation aligned with the code and the actual repo state.
- Do not present aspirational architecture as implemented reality.
- When documenting future plans, label them clearly as planned rather than complete.
- If a file is a private planning note, do not automatically treat it as public-facing material.

---

## Session Completion

Before ending a substantial work session:

1. Summarize what changed.
2. List verification you actually ran.
3. Call out remaining risks, follow-ups, or unknowns.
4. Release any file reservations you no longer need.
5. Sync beads if you changed task state.

---

## Practical Default

When in doubt:

- be conservative with destructive actions
- prefer clarity over speed
- prefer small diffs over sweeping rewrites
- verify what you changed
- ask before making irreversible decisions
