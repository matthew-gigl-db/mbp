# Generic Prompt Examples

**Date:** 2026-10-23

## Problem

The `docs/prompts/` directory contained only `agenticTrading-follow-up-build.md` — a project-specific prompt hardcoded with trading app errors, branch names, SPN IDs, and OTel table paths. It was not reusable across other projects and was too specific to the agenticTrading project.

The framework needed generic, copy-pasteable prompt templates for the three most common Genie Code sessions: starting a new project, planning a follow-up build after the initial build completes, and repairing a failed wave.

## Root Cause

The follow-up prompt was written for a single project's context. No generic templates existed for the three primary workflows the framework supports.

## Changes

### Removed

* `docs/prompts/agenticTrading-follow-up-build.md` — project-specific, not reusable

### Added

* `docs/prompts/new-project.md` — Generic prompt for kicking off an initial build: read framework docs, analyze project, decompose into waves/sessions, write plans and manifest, deploy with `--var` flags, run setup/smoke/build. Uses bracketed `[placeholders]` for all project-specific values.

* `docs/prompts/follow-up-build.md` — Generic prompt for adding convergence waves after a completed initial build: read gate output (`.build-status/<run_id>/wave_*_gate.json`) and session summaries, identify failures and unfulfilled cross-session requests, append parallel fix waves + sequential converge waves with `runtime_targets` and `runtime_gate`, plan files with `## Known issues` sections. Covers the full converge session lifecycle: deploy, read telemetry, fix within `owned_paths`, redeploy until stable.

* `docs/prompts/repair-failed-wave.md` — Generic prompt for re-starting the build from a failed wave: diagnose from gate JSON and status files, `repair_run` with correct `rerun_tasks` (sessions/integrate/gate) and `rerun_dependent_tasks=True`, fresh-run fallback when job structure changed (using `only` parameter), transient agent error retries (`max_retries`), convergence commit-then-fail handling.

### Updated

* `README.md` — Added "Prompt examples" section (line 104) between the planner skill section and Quick start, linking to all three new prompt files with one-line descriptions and a note about replacing bracketed placeholders.

## Decisions

* All three prompts use `[bracketed placeholders]` instead of hardcoded values — works for any project, any workspace, any build target.
* The follow-up prompt preserves the structure of the original agenticTrading prompt (read build output, identify errors, plan waves) but replaces all project-specific details with generic guidance and placeholders.
* The repair prompt consolidates the README's "When a wave fails" section into a standalone copy-pasteable format with SDK code examples and CLI equivalents.
* Placed the "Prompt examples" section in README after the planner skill description (line 104) so users see the prompts right after learning about the planner, before the manual quick start.

## Files Modified

* `docs/prompts/agenticTrading-follow-up-build.md` — deleted
* `docs/prompts/new-project.md` — created
* `docs/prompts/follow-up-build.md` — created
* `docs/prompts/repair-failed-wave.md` — created
* `README.md` — added Prompt examples section at line 104
