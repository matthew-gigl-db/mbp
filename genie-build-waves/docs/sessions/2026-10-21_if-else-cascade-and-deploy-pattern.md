# Session: If/else Cascade Stop and Deploy Pattern

**Date:** 2026-10-21  
**Branch:** `mg-genie-build-waves-init`  
**Commits:** `25aa240`, `973ed14` (outcome fix), `--var` refactor, placeholder restore, iteration labels

## Problem

The first real sGt build run (`675802846673302`) revealed that when a wave gate failed, all downstream integrators still ran with `run_if: ALL_DONE` — each burning 3-8 minutes of Genie Code compute doing nothing. The `ALL_DONE` condition treats `Upstream failed` and `Skipped` as terminal states ("done"), so integrators fired on cascade even though their upstream sessions never ran.

## Research: `run_if` Options

Databricks Jobs supports six `run_if` conditions:

| Condition | Behavior on cascade |
|---|---|
| `ALL_SUCCESS` (default) | Skips correctly, but also skips when sessions fail within a wave (loses status reporting) |
| `NONE_FAILED` | Same issue — can't distinguish "my dep failed" from "my dep was skipped" |
| `ALL_DONE` (our original) | Always runs — correct for within-wave failures, wasteful on cascade |
| `AT_LEAST_ONE_FAILED` | Runs on cascade too (Upstream_failed counts as "failed") |

No single `run_if` distinguishes "sessions actually ran and some failed" from "sessions were skipped by cascade." The `run_if` is per-task, not per-dependency.

**Key finding:** The Excluded propagation rule — "if ALL of a task's dependencies are Excluded, the task itself is Excluded, regardless of its run_if" — cascades along linear chains at zero compute.

## Solution: If/else Condition Tasks

Added a 4th phase per wave: an If/else condition task after each gate notebook.

**Before:** `sessions → integrate (ALL_DONE) → gate [raises on fail]`  
**After:** `sessions → integrate (ALL_DONE) → gate [sets taskValue] → gate_check (If/else)`

### Changes

1. **Gate notebook** (`wave_gate_check`) — no longer raises on failure. Sets `dbutils.jobs.taskValues.set("gate_passed", "true"/"false")` and exits cleanly via `dbutils.notebook.exit()`. The condition task reads the value.

2. **`generate_wave_tasks()`** in setup notebook — adds a `condition_task` after each gate:
   ```python
   tasks.append({
       "task_key": f"{prefix}_gate_check",
       "condition_task": {
           "op": "EQUAL_TO",
           "left": "{{" + f"tasks.{prefix}_gate.values.gate_passed" + "}}",
           "right": "true",
       },
       "depends_on": [{"task_key": f"{prefix}_gate"}],
   })
   ```

3. **Outcome field** — discovered (by sGt session, run `846370512643063`) that depending on a condition_task requires `"outcome": "true"` in the dependency. Without it: `"The dependency on an if/else condition w0_gate_check does not specify an outcome."`

### Cascade behavior

- **Gate passes:** condition evaluates true → next wave sessions run (on the "true" branch)
- **Gate fails:** condition evaluates false → next wave sessions are **Excluded** → all downstream tasks Excluded via propagation → zero compute

**Confirmed in sGt run `842455926421383`:** waves 3-5 (12 tasks) all showed Excluded at 0.0 minutes after wave 2 gate failed.

## Deploy Pattern: `--var` Flags

The sGt planner session independently discovered that passing `--var` flags at deploy time is better than editing `databricks.yml`. Adopted as the primary recommendation:

```bash
databricks bundle deploy --target dev \
  --var="project_name=My App" \
  --var="build_root=/Workspace/Users/you@example.com/my-project" \
  ...
```

**Why:** The bundle is a shared, reusable tool. Project-specific values in `databricks.yml` would require Git changes for each consumer. `--var` flags keep the YAML generic.

**Compromise:** dev/prod targets retain example placeholder values so `bundle validate --strict` passes without `--var` flags, but they're clearly commented as placeholders.

### Files modified

- `databricks.yml` — removed project-specific dev values, added `--var` example comments, restored example placeholders
- `README.md` — 4-phase diagram, `--var` deploy instructions, zero-compute cascade in design decisions, repair instructions include `gate_check`
- `src/notebooks/wave_gate_check.ipynb` — taskValues instead of raise
- `src/notebooks/setup_build_waves_job.ipynb` — condition_task generation, outcome field, session titles in inputs
- `src/skills/genie-build-planner/SKILL.md` — Step 7 "Deploy with --var flags", Step 9 validate with --var
- `resources/build_waves_smoke.job.yml` — nonce field in inputs

## Iteration Labels

`for_each` iterations show "Iteration N" in the UI — there's no way to customize the label. Tested with a toy job: the `description` field does NOT resolve `{{input.*}}` templates (stores them literally). However, enriched inputs (`session_id` + `title`) are visible when clicking into an iteration's details. Left the unresolved description template in place — harmless and would light up if the platform adds support.

## Decisions

- If/else condition tasks are the correct Databricks primitive for cascade control
- Gate notebook must NOT raise — exit cleanly so the condition task can read the taskValue
- `--var` flags at deploy time, not YAML editing, for project-specific values
- Example placeholders in YAML so `bundle validate` passes standalone
