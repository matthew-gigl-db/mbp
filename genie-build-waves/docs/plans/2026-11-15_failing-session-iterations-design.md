# Design note: make a failed session's iteration fail, so a repair re-runs it

**Status:** design idea, not scheduled. The monitor skill uses the fresh-run workaround today (section 8 step 4).
**Date:** 2026-11-15
**Related:** `src/skills/genie-build-monitor/SKILL.md` (sections 4, 6, 8), `docs/prompts/repair-failed-wave.md`, `docs/manifest-schema.md` (Continuation Passes), `src/notebooks/waves_manifest.py` (wave task graph).

## Problem

Each wave's `w<w>_sessions` is a `for_each` task whose nested task is the session runner (a Genie Code task). A Genie Code task ends SUCCESS when the agent finishes, whatever the session wrote to its status file (`pass`, `fail`, `blocked`, `error`). Jobs repairs keep iterations that ended SUCCESS. So after a fix to a session's own files, a repair from `w<w>_sync` pulls the fix but re-runs nothing in `w<w>_sessions`; the fix is never deployed and the gate fails again.

Observed in an end-to-end monitor test: the repair pulled the fix (`SYNC_PULLED`), the sessions step reused the earlier iteration in about 2 seconds, and the gate failed with the same error. A fresh run with `only` = the failed wave's tasks, later waves and `build_verdict` passed.

Today's workaround (owners: README "Why not repair?"; level 4 monitor: section 8 step 4) is that fresh run. It works but re-runs every session in the wave, needs a new run id, and does not help people or monitors who repair by hand.

## Constraint

A Genie Code task cannot be made to fail from inside: the task reports a conversation and a final response ([Genie Code task for jobs](https://docs.databricks.com/aws/en/jobs/tasks/genie-code/)), and there is no documented way for the agent to set the task result. A `for_each` task runs exactly one nested task per iteration, and the nested task cannot be another `for_each` ([Use a For each task](https://docs.databricks.com/aws/en/jobs/tasks/for-each/)). So a status check cannot be added to the iteration directly.

## Option A: per-session child job

The nested task becomes a **Run Job** task that starts a small per-instance **session job**:

```
session job (parameters: session_id, wave, parent_run_id, continuation, branch, build_root, manifest_path)
  session        Genie Code task (session runner, same prompt and parameters as today)
  status_check   notebook, run_if ALL_DONE: read <status_dir>/<parent_run_id>/<session_id>.json;
                 raise when status is fail or error; succeed for pass, blocked and a missing or
                 non-final status (continuation passes handle those)
```

A session that ends `fail` or `error` now fails its child run, so its iteration fails, `w<w>_sessions` fails, and a repair from `w<w>_sync` re-runs only the failed iterations, which start new child runs with the pulled fix.

What changes:

* **Bundle:** a new job resource (placeholder task, like the build job), its permissions block (the monitor needs `CAN_VIEW` to read session outputs), `max_concurrent_runs` at least the largest wave concurrency.
* **Setup:** reset the session job with the runner's Genie Code configuration, as it does for the build job.
* **Task graph (`waves_manifest.py`):** the sessions and continuation `for_each` tasks get a Run Job nested task with `job_parameters` from `{{input...}}`. Pass the parent run id explicitly: inside the child, `{{job.run_id}}` is the child's id, and status files are keyed by the build run id.
* **Downstream:** none needed for dependencies. `w<w>_find_incomplete` and `w<w>_integrate` already use `run_if: ALL_DONE`, so a failed sessions task still lets the continuation pass, integrator and gate run.
* **Gate, find-incomplete, monitor:** session conversation links and outputs move one level down (child run tasks). The gate reads status files, which do not move. The monitor skill's section 1 and 2 (task outputs) need the extra hop.
* **Task count:** child-job tasks do not count toward the build job's 1,000-task limit (a small gain).
* **Blocked sessions:** keep them SUCCESS. A repair cannot clear a manual prerequisite.

Risks and checks:

* Verify that repairing a `for_each` task re-runs only its failed iterations and that a failed Run Job iteration starts a new child run.
* Verify Genie Code task behaviour inside a child job started by Run Job (identity, retries, the task inheriting the owner's Genie Code settings and MCP connections).
* Child runs add start-up time per session.
* The integrator must still commit passing sessions when a sibling failed (it does today; the sessions task failing must not change its inputs).

## Option B: let the continuation pass retry failed sessions after a fix

Cheaper, more fragile. `w<w>_find_incomplete` today lists sessions with no final status. On a repair after a pushed fix (the wave's sync reports `SYNC_PULLED`), it would also list `fail` and `error` sessions whose `owned_paths` the pulled commits touch. A continuation task that was Excluded in the original run (nothing incomplete) is not SUCCESS, so a repair runs it and it picks up the new inputs.

Caveats:

* Only works if that continuation task did not already run in the original attempt; if it did (some other session was incomplete), its SUCCESS iterations are kept.
* The runner treats `continuation=k` as "resume from `progress.next`"; a retry after a fix needs a different mode (start the session's task again with the new code).
* Consumes a continuation pass.

## Recommendation

Keep the fresh-run workaround until a project needs plain repairs to work for owners or level 2-3 monitors. If so, prefer Option A after the two verification checks; Option B only as an experiment.
