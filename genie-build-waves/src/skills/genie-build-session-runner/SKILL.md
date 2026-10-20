---
name: genie-build-session-runner
description: Runs one session of a project as an unattended Genie Code job task inside a for_each wave. Reads the session definition from a waves.json manifest, executes the referenced plan (editing files, running notebooks, configuring resources, or any combination), validates, and writes a machine-readable status file. Supports git, workspace, and hybrid workflow modes. Use when a job task passes session_id, wave, run_id, branch, build_root and manifest_path.
---

# Session Runner

You are one of several Genie Code sessions running **in parallel** on the same project. You run unattended with auto-approve, so the guardrails below are hard rules, not suggestions. Your job: complete exactly one session plan, within your ownership boundaries, then report.

## Inputs (from the job task parameters)

| Parameter | Meaning |
|---|---|
| `session_id` | Session to run, e.g. `01`, `06a`, `13` |
| `wave` | Wave id, e.g. `0`, `1`, `4a` |
| `run_id` | Job run id. Used to namespace status files |
| `branch` | Feature branch (for `git`/`hybrid` workflows; may be empty for `workspace` mode) |
| `build_root` | Absolute workspace path of the project |
| `manifest_path` | Absolute path of `waves.json` |

If any required parameter is missing or still looks like a `{{placeholder}}`, stop and write a status file with `status: "error"` (step 7) if you can, then end.

## Guardrails (hard rules)

Guardrails 1–3 apply based on the **workflow mode** (from `manifest.workflow.mode`, default `git`) and **session mode** (from session `mode`, default `edit`).

### Always apply (all modes)

1. **Read-only for shared docs.** Do not edit plan files (`plans_dir/**`), session index files (`sessions_dir/INDEX.md`), project memory files (`PROJECT_MEMORY.md`), collaboration folders (`hi_genie/**`), or the manifest (`waves.json`).
2. **Data and secrets.** Never write or print secret values. Never run DROP, TRUNCATE or DELETE on Unity Catalog or Lakebase objects that you did not create in this session.
3. **No scope creep.** Do only the `scope` text for your session. If the plan file and the manifest `scope` disagree, the manifest wins; note the conflict in your status file.
4. **Fail loud, not silent.** If you cannot finish, still write the summary and status file with what was done and what is blocking.

### Git guardrails (workflow `git` or `hybrid`)

5. **Git: read-only.** Never commit, push, pull, checkout, switch, merge, rebase, reset, stash or discard. Other sessions share this working tree; any of those would destroy their work. The wave integrator commits.
6. **Never touch `main`.** If `branch` is `main` or `master`, or the Git folder is not on `branch`, stop with `status: "error"`. Do not switch branches.

### Ownership guardrails (by session mode)

7. **`edit` mode (default):** Create, edit or delete files only if they match your session's `owned_paths` and do not match `exclude_paths` (globs relative to `build_root`). The two exceptions are your summary and status files (steps 6-7). Changes outside your paths go to `requests` in your status file.
8. **`execute` mode:** Run notebooks, SQL queries, SDK calls, or CLI commands as described in your plan. You may create output artifacts (tables, model versions, dashboard widgets) listed in `owned_assets`. Do not edit project source files unless they are also in your `owned_paths`.
9. **`configure` mode:** Configure Databricks resources (jobs, pipelines, endpoints, permissions, secrets) as described in your plan. Resources you modify should be listed in `owned_assets`.

### Deploy and execute guardrails

10. **Deploys.** Only if your session has `allow_deploy: true`, and only with the target specified in `bundle_target`. Never deploy or destroy anything on a target not listed. Never run `bundle destroy`.
11. **Execution.** Only if your session has `allow_execute: true` (default for `execute`/`configure` modes, false for `edit` mode). When executing notebooks or SQL, do not modify objects outside your `owned_assets`.

## Steps

### 1. Load your session

Read `manifest_path`. Find the wave whose `wave_id` equals `wave` and, inside it, the session whose `session_id` equals `session_id`.

Keep from the session: `title`, `plan_file`, `scope`, `mode` (default `edit`), `owned_paths`, `owned_assets`, `exclude_paths`, `allow_deploy`, `allow_execute`, `depends_on`.

Keep from the manifest top level: `workflow` (default `{"mode": "git"}`), `bundle_target`, `status_dir`, `plans_dir`, `sessions_dir`, `repo_root` (default: `build_root`), `context_files`.

Determine your effective mode:
- `workflow_mode` = `manifest.workflow.mode` or `"git"`
- `session_mode` = session `mode` or `"edit"`

If the session is not found, stop with `status: "error"`.

### 2. Check the branch (git/hybrid only)

If `workflow_mode` is `git` or `hybrid`:
- Use the Git tooling read-only (status/current branch) on `repo_root`. It must be on the `branch` parameter. If not, or if `branch` is `main`/`master`, stop (guardrail 6).

If `workflow_mode` is `workspace`: skip this step entirely.

### 3. Read context, in this order

1. `repo_root/PROJECT_MEMORY.md` and, if present, `repo_root/hi_genie/` (read-only collaboration notes; follow any pending recommendation that applies to your session).
2. The project's plan index (`build_root/<plans_dir>/INDEX.md`): wave plan, dependency graph, hidden dependencies, shared-file table, resolved gaps.
3. Your plan file (`build_root/<plans_dir>/<plan_file>`): only the tasks named in `scope` apply.
4. Session summaries of your `depends_on` sessions in `build_root/<sessions_dir>/` (latest file whose name contains `-<dep_id>-`), to learn what they actually produced.
5. For `edit` sessions: the current contents of every file you are about to change.
6. For `execute`/`configure` sessions: the current state of every asset you will modify (read tables, inspect resources).

If the manifest contains a `context_files` list, read those too — they provide project-specific conventions, coding standards, data dictionaries, or architectural decisions.

### 4. Do the work

Based on your `session_mode`:

**`edit` mode:**
- Follow the existing code style; preserve comments.
- Use the workspace file tools for all edits; never use shell commands to write files.
- Parallel dependencies: if you import from a file another session in the **same wave** owns and it does not exist yet, code against the signature documented in its plan, and record it under `assumptions`.

**`execute` mode:**
- Create and/or run notebooks, SQL queries, or SDK scripts as described in your plan.
- Record outputs (table row counts, model metrics, query results) in your session summary.
- If execution fails, capture the error in your status file and mark `status: "fail"`.

**`configure` mode:**
- Create, update, or configure the Databricks resources described in your plan.
- Verify each resource reached its expected state.
- Record resource ids, endpoints, or URIs in your session summary for downstream sessions.

**All modes:** Follow any project-specific conventions found in `context_files` or `PROJECT_MEMORY.md`.

### 5. Validate

Run every acceptance-criteria check from your plan. Typical checks by mode:

**`edit`:** `bundle validate --strict --target <bundle_target>` if you touched YAML. Language-specific checks (typecheck, lint, test) if available.
**`execute`:** Verify outputs exist and pass quality checks (row counts, schema matches, metric thresholds).
**`configure`:** Verify resources are in expected state (running, active, accessible).

Deploy-time checks only when `allow_deploy` is true. A check you did not run does not count as passed.

### 6. Write your session summary

Path: `build_root/<sessions_dir>/<YYYY-MM-DD>_w<wave>-<session_id>-<short-slug>.md`. Get the date from `datetime.now()`. Content: problems, root causes, changes, decisions, files modified or assets created, checks run with results, requests for other sessions. Do not edit `<sessions_dir>/INDEX.md`; the integrator does.

### 7. Write your status file

Path: `build_root/<status_dir>/<run_id>/<session_id>.json`. Exactly this shape:

```json
{
  "session_id": "03",
  "wave": "1",
  "run_id": "123456",
  "mode": "edit | execute | configure",
  "status": "pass | fail | blocked | error",
  "summary_file": "docs/sessions/2026-10-21_w1-03-lakebase-migrations.md",
  "files_changed": ["server/migrations/migrate.ts"],
  "assets_changed": ["catalog.schema.my_table"],
  "checks": [{"name": "bundle validate --strict", "result": "pass | fail | skipped", "detail": ""}],
  "assumptions": [],
  "requests": [{"path": "package.json", "change": "add dependency x@1.2", "why": ""}],
  "blocking": ""
}
```

`status` is `pass` only if the scope is complete and no check failed. `files_changed` lists files created/edited/deleted (relative to `build_root`). `assets_changed` lists non-file assets created or modified (tables, notebooks, resources). Both exclude the summary and status files.

### 8. Final response

End with at most 5 lines: `session_id`, `mode`, `status`, number of files/assets changed, failed or skipped checks, and the status file path. This text becomes the task output.

## Edge cases

- **Session already done** (summary + status `pass` for an earlier `run_id`, and the outputs match the plan): re-validate, then write a new status file for this `run_id` with `status: "pass"` and note "already completed".
- **Manual prerequisite missing** (e.g. a dependency that requires work outside Genie Code): do what you can, mark `status: "blocked"`, and name the prerequisite in `blocking`.
- **Another session's output is broken**: do not fix it. Record it under `requests`.
- **Workspace mode with no Git folder**: skip all Git checks. Your working directory is `build_root` but you may create/modify assets anywhere within your `owned_assets`.
