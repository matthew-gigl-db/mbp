# waves.json Manifest Schema

The manifest is the single source of truth for a project. It defines the workflow mode, waves, sessions, ownership boundaries, gate checks, and concurrency. Every Genie Code session (runner and integrator) reads it at runtime.

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
| `waves` | Wave[] | Yes | Ordered list of waves. Executed sequentially; sessions within a wave run in parallel. |

## Wave Object

| Field | Type | Required | Description |
|---|---|---|---|
| `wave_id` | string | Yes | Unique identifier (e.g. `0`, `1`, `4a`). Used in task keys and file names. |
| `name` | string | No | Human-readable wave name. |
| `concurrency` | integer | No | Max parallel sessions. Defaults to the number of sessions. |
| `manual_prereqs` | ManualPrereq[] | No | Sessions that must be done outside Genie Code before this wave runs. |
| `gate` | string[] | Yes | List of checks the integrator runs after all sessions finish. Plain text descriptions; the integrator interprets them. |
| `sessions` | Session[] | Yes | Sessions in this wave. |

## Session Object

| Field | Type | Required | Description |
|---|---|---|---|
| `session_id` | string | Yes | Unique identifier (e.g. `01`, `06a`). Used in task keys and file names. |
| `title` | string | Yes | Human-readable session title. |
| `plan_file` | string | Yes | Plan file name relative to `plans_dir` (e.g. `01_bundle_scaffold.md`). |
| `scope` | string | Yes | What to do. If the plan file and this field disagree, this field wins. |
| `mode` | string | No | Session mode: `edit` (default), `execute`, or `configure`. See Session Modes. |
| `owned_paths` | string[] | Conditional | Glob patterns (relative to `build_root`) of files this session may create/edit/delete. **Required** for `edit` mode sessions in `git`/`hybrid` workflows. Not used in `workspace` mode or `execute`/`configure` sessions. |
| `owned_assets` | string[] | No | Asset identifiers this session may create or modify (e.g. notebook paths, table names, dashboard ids). For `execute`/`configure` sessions. Informational — the runner uses them for self-auditing. |
| `exclude_paths` | string[] | No | Glob patterns to exclude from `owned_paths`. |
| `allow_deploy` | boolean | No | Whether the session may run `bundle deploy`. Defaults to `false`. |
| `allow_execute` | boolean | No | Whether the session may execute notebooks or run SQL. Defaults to `false` in `edit` mode, `true` in `execute`/`configure` mode. |
| `depends_on` | string[] | No | Session ids that must be done before this session. Enforced by wave ordering, not runtime — all deps should be in prior waves. |

## Session Modes

| Mode | What the session does | Ownership | Git tracking |
|---|---|---|---|
| `edit` (default) | Creates, modifies, or deletes files in the project | `owned_paths` (enforced) | Files committed by integrator |
| `execute` | Runs notebooks, SQL queries, SDK calls, or CLI commands | `owned_assets` (advisory) | Not committed — output is the deliverable |
| `configure` | Configures Databricks resources (jobs, pipelines, endpoints, permissions) | `owned_assets` (advisory) | Not committed — resource state is the deliverable |

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

## Use Case Examples

| Use Case | Workflow Mode | Session Modes | Example Gate |
|---|---|---|---|
| Build a DABs bundle | `git` | `edit` | `bundle validate --strict` passes |
| Build a Databricks App | `git` | `edit` + `configure` | App starts without crash |
| Data engineering pipeline | `workspace` | `execute` | All target tables have >0 rows |
| ML model training | `workspace` | `execute` | Model logged to MLflow with accuracy > 0.85 |
| Platform migration | `hybrid` | `edit` + `execute` | Source and target row counts match |
| Infrastructure setup | `workspace` | `configure` | All schemas, volumes, and grants exist |
| Documentation generation | `git` | `edit` | All markdown files pass lint |
| Testing campaign | `workspace` | `execute` | All test notebooks pass |
