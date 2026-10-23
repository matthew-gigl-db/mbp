# Repair Failed Wave — Re-starting from a Specific Wave

> Paste this into Genie Code in your **project** folder (or the bundle repo) when a build
> run has a failed wave and you need to repair it. This prompt covers both the repair_run
> workflow and the fresh-run fallback when the job structure has changed.
> Replace the bracketed placeholders with your run's details.

---

## Prompt

The build run `[run_id]` on job `[job_id]` has a failed wave `[wave_number]`. I need to repair the run and re-execute from the failed wave onward.

### Step 1: Diagnose the failure

Before repairing, understand what went wrong:

1. Read the `w[wave_number]_gate` task output in the run.
2. Read `.build-status/[run_id]/wave_[wave_number]_gate.json` — this lists which checks failed and why.
3. If it's a convergence wave, also read `.build-status/[run_id]/wave_[wave_number]_runtime.json` for deployment IDs, states, and error samples.
4. Read the failing session's status file and summary in `docs/sessions/`.
5. Check for `requests` in the gate file — these list changes a session needed outside its owned paths. Apply them before repairing.
6. Passing sessions are already committed (in `git`/`hybrid` mode). Failing sessions' code is left uncommitted.
7. Fix the root cause (plan, manifest, or code) before attempting the repair.

Note: downstream waves show as **Excluded** (not failed). This is correct cascade behavior — they never ran and consumed no compute.

### Step 2: Repair the run

Once the cause is fixed, repair from the failed wave's tasks onward. The key rule: **always include `rerun_dependent_tasks=True`** so that `wN_gate_check` and every later wave re-evaluates.

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
w.jobs.repair_run(
    run_id=[run_id],
    rerun_tasks=["w[wave_number]_sessions", "w[wave_number]_integrate", "w[wave_number]_gate"],
    rerun_dependent_tasks=True,  # re-runs wN_gate_check and every later wave
)
```

CLI equivalent:

```bash
databricks jobs repair-run [run_id] --json '{"rerun_tasks": ["w[wave_number]_sessions", "w[wave_number]_integrate", "w[wave_number]_gate"], "rerun_dependent_tasks": true}'
```

If the run was already repaired once, also pass `latest_repair_id`:
```python
repair_history = w.jobs.get_run(run_id=[run_id], include_history=True).repair_history
# Use the latest repair_id from repair_history
```

In the UI: choose **Repair run** and select the failed wave's tasks **and** everything after them, including each `wN_gate_check`.

### Which tasks to rerun

| What failed | `rerun_tasks` |
|---|---|
| A session (code, plan, or manifest fixed) | `w[wave_number]_sessions`, `w[wave_number]_integrate`, `w[wave_number]_gate` |
| Only the integrator (sessions passed) | `w[wave_number]_integrate`, `w[wave_number]_gate` |
| Only the gate verdict (e.g. stray files, runtime soak) | `w[wave_number]_gate` |

Keep `rerun_dependent_tasks=True` in every case. Without it, nothing after the named tasks runs.

### Step 3: Fresh run fallback

If the build job was redeployed and re-patched since the failed run, Jobs refuses to repair it ("job structure has changed"). Start a new run with `only` set to the failed wave's task keys and everything after it:

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# List all task keys from the failed wave onward
only_tasks = [
    "w[wave_number]_sessions", "w[wave_number]_integrate", "w[wave_number]_gate", "w[wave_number]_gate_check",
    # ... all tasks from later waves too
]

w.jobs.run_now(
    job_id=[job_id],
    only=only_tasks,
)
```

Earlier waves show as SKIPPED. Files left in the working tree by the earlier run (uncommitted summaries, code from failed sessions) are reported by the integrator as `carryover_files`, not strays, so they no longer fail the new run's first gate. Summary carryover is committed; code carryover is left for the session that owns it. The last wave fails on any carryover code nobody claimed, so a human decides what to do with it.

### Step 4: Transient agent errors

**Transient agent start-up errors** (`INTERNAL_ERROR: start_agent_run`) are retried automatically: Genie Code tasks get `max_retries` (default 2, one minute apart, override with manifest `task_retries`). If a task still fails after its retries, repair as above — don't start a fresh run.

### Step 5: Convergence wave failures

A convergence wave can commit (its session passed) and still fail on `runtime_gate` (e.g. the app crashed during the soak). The commit is kept as progress; repair re-runs the converge session, which starts from the committed code.

---

_This prompt is generic. Adapt the placeholders for your run ID, job ID, and wave number._
