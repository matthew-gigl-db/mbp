# waves.json Manifest Schema

The manifest is the single source of truth for a project. It defines the workflow mode, waves, sessions, ownership boundaries, gate checks, concurrency, and (for follow-up builds) the runtime targets that must deploy and run stably. Every Genie Code session (runner and integrator) and the deterministic gate notebook read it at runtime.

## Build Phases

A project typically goes through two phases. Both use the same manifest format and job; they differ in session mode and gate type.

| Phase | Session mode | Wave shape | Gate | Pass means |
|---|---|---|---|---|
| **Initial build** | `edit` / `execute` / `configure` | Wide, parallel, disjoint `owned_paths` | Static (`gate` text: validate, file checks) | Files exist, bundle validates |
| **Convergence** (follow-up) | `converge` | One session per wave, sequential | Static `gate` + deterministic `runtime_gate` | The target deploys, runs, and stays stable; logs are clean |

The initial build gets breadth quickly; convergence makes it actually work. A deployed resource has one live state, so deploy-fix-redeploy loops must never run in parallel. Convergence waves are therefore single-session by rule (enforced by the setup notebook).

Append convergence waves to the existing manifest (keep the earlier waves for history; run the build with `only` set to the new wave task keys, or start a new run once earlier waves are already committed — passing sessions are idempotent and re-validate as "already completed").

## Workflow Modes

The manifest supports three workflow modes that control how sessions operate and how integration works:

| Mode | Sessions write to | Integrator commits | Use for |
|---|---|---|---|
| `git` (default) | Files in a Git folder | Yes, by explicit path to a feature branch | Building DABs bundles, app code, any Git-tracked project |
| `workspace` | Notebooks, queries, tables, dashboards, UC objects | No Git — status collection and gates only | Data engineering, ML pipelines, migrations, infra setup, analysis |
| `hybrid` | Mix of file edits and workspace operations | Commits file edits only; workspace sessions skip Git | Projects that combine code authoring with notebook execution or SQL work |

## Top-Level Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | integer | Yes | Schema version. Currently `1`. |
| `description` | string | No | Human-readable description of this project. |
| `workflow` | Workflow | No | Workflow mode and Git settings. Defaults to `{"mode": "git"}`. |
| `repo_root` | string | No | Absolute workspace path of the Git folder root. Only used in `git`/`hybrid` modes. Defaults to `build_root` if omitted. |
| `bundle_root` | string | No | Absolute workspace path of the project root. Informational; the job parameter `build_root` is the runtime authority. |
| `branch` | string | No | Default feature branch. Only used in `git`/`hybrid` modes. Informational; the job parameter `branch` is the runtime authority. |
| `bundle_target` | string | No | The DABs target for validation and deploy checks (e.g. `dev`). Required for `git`/`hybrid` modes when sessions touch bundle YAML. |
| `status_dir` | string | Yes | Directory for status and gate files, relative to `build_root`. Convention: `.build-status`. Never committed to Git. |
| `plans_dir` | string | Yes | Directory containing plan files, relative to `build_root`. Convention: `docs/plans`. |
| `sessions_dir` | string | Yes | Directory for session summaries, relative to `build_root`. Convention: `docs/sessions`. |
| `context_files` | string[] | No | Extra files (relative to `build_root`) for sessions to read before working. Project memory, coding standards, architecture docs, data dictionaries, model cards. |
| `skills` | object | No | Overrides for skill locations. See Skills section. |
| `task_retries` | object | No | Automatic retries for Genie Code tasks (sessions and integrators), for transient agent start-up errors such as `INTERNAL_ERROR: start_agent_run`. Keys: `max_retries` (default `2`; `0` disables), `min_retry_interval_seconds` (default `60`). Timeouts are never retried. Gate notebooks are not retried. |
| `runtime_targets` | map<string, RuntimeTarget> | No | Deployable things (apps, jobs, pipelines, dashboards) that `converge` sessions deploy and `runtime_gate` checks. Keyed by a short target name. See RuntimeTarget. |
| `waves` | Wave[] | Yes | Ordered list of waves. Executed sequentially; sessions within a wave run in parallel. |

## Wave Object

| Field | Type | Required | Description |
|---|---|---|---|
| `wave_id` | string | Yes | Unique identifier (e.g. `0`, `1`, `4a`). Used in task keys and file names. |
| `name` | string | No | Human-readable wave name. |
| `concurrency` | integer | No | Max parallel sessions. Defaults to the number of sessions. |
| `manual_prereqs` | ManualPrereq[] | No | Sessions that must be done outside Genie Code before this wave runs. |
| `gate` | string[] | Yes | List of checks the integrator runs after all sessions finish. Plain text descriptions; the integrator interprets them. |
| `runtime_gate` | string[] | No | Names of `runtime_targets` the **gate notebook** checks deterministically after the integrator commits (deployment succeeded in this run, running, soak-stable, clean logs). Required on any wave with a `converge` session. A failing runtime gate fails the wave regardless of what the Genie Code tasks reported. |
| `validate_bundles` | BundleValidation[] | No | Bundles the **integrator** must run `bundle validate --strict` on for this wave, each from its own root and target: `[{"root": "infra", "target": "dev"}, {"root": "app", "target": "dev"}]`. `root` is absolute or relative to `build_root`. Results go in the gate file's `bundle_validations`; the gate notebook fails the wave if any entry is missing or not `pass`. Use this instead of free-text validate lines in `gate` when a wave touches more than one bundle. See Multiple bundles in one manifest. |
| `timeout_minutes` | integer | No | Default task timeout for this wave's sessions. Defaults: 60 (`edit`/`execute`/`configure`), 180 (`converge`). |
| `sessions` | Session[] | Yes | Sessions in this wave. |

## Session Object

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | Yes | Unique identifier (e.g. `01`, `06a`). Used in task keys and file names. |
| `title` | string | Yes | Human-readable session title. |
| `plan_file` | string | Yes | Plan file name relative to `plans_dir` (e.g. `01_bundle_scaffold.md`). |
| `scope` | string | Yes | What to do. If the plan file and this field disagree, this field wins. |
| `mode` | string | No | Session mode: `edit` (default), `execute`, `configure`, or `converge`. See Session Modes. |
| `owned_paths` | string[] | Conditional | Glob patterns (relative to `build_root`) of files this session may create/edit/delete. **Required** for `edit` and `converge` sessions in `git`/`hybrid` workflows. Not used in `workspace` mode or `execute`/`configure` sessions. |
| `owned_assets` | string[] | No | Asset identifiers this session may create or modify (e.g. notebook paths, table names, dashboard ids). For `execute`/`configure` sessions. Informational — the runner uses them for self-auditing. |
| `exclude_paths` | string[] | No | Glob patterns to exclude from `owned_paths`. |
| `allow_deploy` | boolean | No | Whether the session may run `bundle deploy`. Defaults to `false`. |
| `allow_execute` | boolean | No | Whether the session may execute notebooks or run SQL. Defaults to `false` in `edit` mode, `true` in `execute`/`configure` mode. |
| `depends_on` | string[] | No | Session ids that must be done before this session. Enforced by wave ordering, not runtime — all deps should be in prior waves. |
| `runtime_targets` | string[] | Conditional | **Required** for `converge`. Names of top-level `runtime_targets` this session deploys and must make stable. It may deploy only these. |
| `max_attempts` | integer | No | `converge` only. Max deploy-diagnose-fix iterations before giving up with `status: "fail"`. Default `5`. |
| `timeout_minutes` | integer | No | Task timeout for this session. Overrides the wave default. |
| `context_notes` | string | No | Free-text findings handed over from an interactive Genie Code session (known errors, log excerpts, decisions). The runner reads it as context; `scope` still wins. |

## Session Modes

| Mode | What the session does | Ownership | Git tracking |
|---|---|---|---|
| `edit` (default) | Creates, modifies, or deletes files in the project | `owned_paths` (enforced) | Files committed by integrator |
| `execute` | Runs notebooks, SQL queries, SDK calls, or CLI commands | `owned_assets` (advisory) | Not committed — output is the deliverable |
| `configure` | Configures Databricks resources (jobs, pipelines, endpoints, permissions) | `owned_assets` (advisory) | Not committed — resource state is the deliverable |
| `converge` | Deploys its `runtime_targets`, reads deployment status and telemetry, fixes code within `owned_paths`, and redeploys until stable or `max_attempts` | `owned_paths` (enforced) + `runtime_targets` | Files committed by integrator, same as `edit` |

`converge` implies `allow_deploy: true` and `allow_execute: true` for its own `runtime_targets` only.

## RuntimeTarget Object

Describes how to deploy, run, and observe one deployable resource. Used by `converge` sessions (how to deploy and where to look) and by the gate notebook (what "stable" means).

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `app`, `job`, `pipeline`, or `dashboard`. |
| `name` | string | Conditional | Deployed resource name as it appears in the workspace (app name, or job/pipeline/dashboard display name including any dev-mode prefix). Used by the gate to look it up; a lookup that matches zero or several resources fails. Required for apps; otherwise `name` or `id`. |
| `id` | string | No | Job id, pipeline id, or dashboard id. Preferred over `name` lookup. |
| `bundle_root` | string | No | Absolute workspace path of the bundle that defines the resource. Defaults to `build_root`. |
| `bundle_target` | string | No | Target to deploy. Defaults to top-level `bundle_target`. |
| `resource_key` | string | No | Bundle resource key (e.g. `trading_agent_app`), used for `bundle run <resource_key>`. |
| `deploy_commands` | string[] | No | Databricks CLI commands (without the `databricks` prefix) run from `bundle_root`, in order, to deploy and start the target. Default for apps: `bundle deploy --target <t>` then `bundle run <resource_key> --target <t>` (plain deploy does not redeploy app code when config is unchanged). |
| `telemetry` | Telemetry | No | Where logs land and how to judge them. Strongly recommended for apps. |
| `stability` | Stability | No | Soak and error budget. |
| `require_fresh_deployment` | boolean | No | Gate requires the active deployment / run / update / published dashboard revision to have started after the build job run started. Default `true`. |
| `warehouse_id` | string | No | `dashboard` only. Warehouse for the dataset checks. Defaults to the published dashboard's warehouse. |
| `execute_datasets` | boolean | No | `dashboard` only. `false` (default): validate each dataset query with `EXPLAIN` (no data scanned). `true`: run `SELECT * FROM (<query>) LIMIT 1`, which also catches runtime errors. |
| `dataset_timeout_seconds` | integer | No | `dashboard` only. Per-dataset statement timeout. Default `120`. |

Dashboards deploy with `bundle deploy` alone (deploy publishes them), so `deploy_commands` defaults to `bundle deploy --target <t>` and `resource_key` is not needed.

### Telemetry Object

| Field | Type | Description |
|---|---|---|
| `logs_table` | string | UC table with OpenTelemetry logs (e.g. the app's `telemetry_export_destinations` logs table). Expected OTel columns: `time`, `date`, `severity_text`, `body` (variant), `attributes` (variant). |
| `deployment_id_attribute` | string | Attribute key holding the app deployment id. Default `app.deployment_id`. |
| `log_source_attribute` | string | Attribute key distinguishing build vs runtime logs. Default `app.log_source` (values seen: `BUILD`, `SYSTEM`, `APP`). |
| `error_patterns` | string[] | Regexes (matched against `body`) that count as errors in addition to `severity_text IN ('ERROR','FATAL')`. Default: `error TS\\d+`, `ELIFECYCLE`, `Error building app`, `Unhandled`, `UnhandledPromiseRejection`, `FATAL`. |
| `ignore_patterns` | string[] | Regexes for known-benign lines to exclude from the error count (e.g. `Updated file:`). |
| `required_markers` | string[] | Regexes that must each match at least one runtime log line for the active deployment (e.g. `listening on`, `pollers started`). |

### Stability Object

| Field | Type | Description |
|---|---|---|
| `soak_minutes` | integer | How long the gate watches the target after it is up. During the soak the app must stay `RUNNING` with the same active deployment. Default `10`. |
| `max_errors` | integer | Error-line budget for the active deployment. Default `0`. |

### What the runtime gate checks

| Type | Checks |
|---|---|
| `app` | Active deployment `SUCCEEDED` and (if fresh required) created after the build run started; no pending deployment; `app_status` `RUNNING` and `compute_status` `ACTIVE`; unchanged through the soak; error lines for the active deployment ≤ `max_errors`; every `required_markers` regex matched. |
| `job` | Latest run started after the build run started is `TERMINATED` / `SUCCESS`. |
| `pipeline` | Latest update started after the build run started is `COMPLETED` (or `RUNNING` for continuous pipelines through the soak). |
| `dashboard` | Published, with the published revision created after the build run started; a warehouse is set; every dataset resolves. Query datasets: `EXPLAIN` (default; a plan containing `Error occurred during query planning` fails even though the statement succeeds) or `LIMIT 1` execution with `execute_datasets`, using the dataset's `catalog`/`schema` and default parameter values. Datasets with multi-value or range parameters are reported as `skipped`. Table / metric view datasets (`asset_name`) must resolve in Unity Catalog. No soak. |

### Multiple bundles in one manifest

One root-level manifest can drive several bundles (for example an infra bundle and an app bundle in the same repo):

* Static gates: list each bundle in the wave's `validate_bundles` with its own `root` and `target`. The integrator validates each one; the gate notebook checks every entry was reported as `pass`.
* Deploys: give each runtime target its own `bundle_root` and `bundle_target`. A `converge` session deploys each target from that target's bundle.
* Deploy order across bundles is wave order: put the infra target's `converge` wave before the app's.

## ManualPrereq Object

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | Yes | Identifier for the prerequisite. |
| `title` | string | Yes | Description. |
| `plan_file` | string | No | Reference plan file. |
| `done_when` | string | Yes | Condition the integrator checks to verify completion (e.g. "file X exists on the branch"). |

## Workflow Object

| Field | Type | Required | Description |
|---|---|---|---|
| `mode` | string | No | `git` (default), `workspace`, or `hybrid`. Controls Git guardrails and integration behavior. |

When omitted, the entire `workflow` object defaults to `{"mode": "git"}`.

## Skills Object (optional)

Overrides the default skill locations. If omitted, the setup notebook uses its own bundled skills.

| Field | Type | Description |
|---|---|---|
| `catalog` | string | UC catalog for publishing skills. |
| `schema` | string | UC schema for publishing skills. |
| `runner` | `{skill_id, folder}` | Runner skill: UC skill id and workspace folder containing `SKILL.md`. |
| `integrator` | `{skill_id, folder}` | Integrator skill: UC skill id and workspace folder containing `SKILL.md`. |

## Design Rules

1. **No path overlap within a wave.** In `git`/`hybrid` modes, two `edit`-mode sessions in the same wave must not have overlapping `owned_paths`. This prevents merge conflicts when sessions run in parallel.
2. **No asset overlap within a wave.** In any mode, two sessions in the same wave should not modify the same assets. Use `owned_assets` to document boundaries.
3. **Dependencies across waves only.** `depends_on` references sessions in prior waves. The wave ordering is the enforcement mechanism.
4. **Scope is king.** If `scope` and the plan file disagree, `scope` wins. The runner notes the conflict in its status file.
5. **Gates are human-readable.** Gate check descriptions are interpreted by the integrator Genie Code session. Write them as clear assertions (e.g. "bundle validate --strict --target dev passes", "table X has >0 rows", "notebook Y ran without errors").
6. **Status dir is ephemeral.** `.build-status/` is per-run. In `git`/`hybrid` modes, add it to `.gitignore`.
7. **Deploys are single-writer.** A wave that contains a `converge` session, or any session with `allow_deploy: true`, must contain exactly one session. The setup notebook rejects manifests that break this and forces `concurrency: 1`.
8. **Runtime gates are deterministic.** Every wave with a `converge` session must list its targets in `runtime_gate`. The gate notebook checks them itself; it does not trust session or integrator reports.
9. **Don't put the build job in the bundle being converged.** If a `converge` session deploys a bundle that also defines the build-waves job, the deploy resets the running build job. Keep orchestration in the genie-build-waves bundle.

## Use Case Examples

| Use Case | Workflow Mode | Session Modes | Example Gate |
|---|---|---|---|
| Build a DABs bundle | `git` | `edit` | `bundle validate --strict` passes |
| Build a Databricks App | `git` | `edit` + `configure` | App starts without crash |
| Make an app build/deploy stable | `git` | `converge` | `runtime_gate`: app RUNNING, soak-stable, no error logs |
| Data engineering pipeline | `workspace` | `execute` | All target tables have >0 rows |
| ML model training | `workspace` | `execute` | Model logged to MLflow with accuracy > 0.85 |
| Platform migration | `hybrid` | `edit` + `execute` | Source and target row counts match |
| Infrastructure setup | `workspace` | `configure` | All schemas, volumes, and grants exist |
| Documentation generation | `git` | `edit` | All markdown files pass lint |
| Testing campaign | `workspace` | `execute` | All test notebooks pass |
