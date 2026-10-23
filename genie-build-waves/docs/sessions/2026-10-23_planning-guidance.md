# Planning Guidance Improvements (Batch C)

**Date:** 2026-10-23

## Problem

Feedback from a consumer Genie Code session identified three planning and lifecycle issues:

1. **Static gates miss runtime schema bugs.** A missing `votes.version_hash` column and a `current_campaign_id` mistake both passed static gates (bundle validate, file existence) and only surfaced at deploy time.

2. **Converge sessions can run out of turns.** Session 12 ran 42 minutes converging multiple targets and needed two manual continues. Splitting into one target per wave (29 and 27 minutes with no resumes) worked better.

3. **After a merge, the job's defaults still point at the deleted branch.** The integrator had no check for branch existence on the remote, and the docs had no retarget-after-merge guidance.

## Root Cause

1. The planner skill did not explicitly call out migrations as a high-risk case requiring convergence or table checks.
2. The planner said "one converge wave per runtime target" but did not enforce one `runtime_targets` entry per session, and had no attempt-budget guidance.
3. The integrator checked the local branch but not the remote. No docs covered the post-merge retarget workflow.

## Changes

### src/skills/genie-build-planner/SKILL.md

* Updated convergence guidance: "One converge session per runtime target" with exactly one entry in `runtime_targets`. Added explicit warning that converging multiple targets runs out of Genie Code turns.
* Added attempt-budget guidance: 25-35 minutes per target with `max_attempts: 5`; lower `max_attempts` if more than 3 attempts expected.
* Added tip: "Migrations need convergence" — edit waves touching database migrations, SQL DDL, or schema files must be followed by a table runtime target check or a converge wave.

### src/skills/genie-build-wave-integrator/SKILL.md

* Added branch-on-remote check in step 1: on the first wave in git/hybrid mode, check that `branch` exists on the remote via `git ls-remote --heads origin <branch>`. If not found, write a fail gate with a retarget message and stop.

### docs/prompts/repair-failed-wave.md

* Added "Retarget after merge" section with 5-step procedure: new branch, update manifest, re-deploy, re-run setup, new run.

### README.md

* Added "Retarget after merge" section with the same procedure.

## Decisions

* The automated "compare SQL column references against migrations" check suggested in the feedback was not implemented — too project-specific for the framework. Instead, the planner guidance now explicitly recommends convergence after migration-touching waves.
* The branch-on-remote check runs only on the first wave to avoid repeating the `git ls-remote` call on every wave (the branch won't disappear mid-run).
* The retarget section is added to both the repair prompt and the README for discoverability.

## Files Modified

* src/skills/genie-build-planner/SKILL.md — one target per converge session, attempt budget, migrations tip
* src/skills/genie-build-wave-integrator/SKILL.md — branch-on-remote check
* docs/prompts/repair-failed-wave.md — retarget after merge section
* README.md — retarget after merge section