# genie-build-waves

A reusable Declarative Automation Bundle that orchestrates parallel Genie Code sessions to do any kind of work inside Databricks. Decompose any large project — code builds, data pipelines, ML training, migrations, infrastructure setup — into dependency-ordered waves. Run sessions in parallel within each wave, and gate progression with deterministic quality checks.

## What you can build with this

* **DABs bundles and apps** — Author code in parallel sessions, commit per wave (`git` mode)
* **Data engineering pipelines** — Create tables, run notebooks, validate outputs (`workspace` mode)
* **ML model training** — Parallel EDA, feature engineering, and model training with champion selection
* **Platform migrations** — Move workloads from external platforms into Databricks
* **Infrastructure setup** — Create schemas, volumes, endpoints, grants across environments
* **Testing campaigns** — Run validation notebooks in parallel, gate on pass/fail
* **Documentation** — Generate docs, diagrams, or reports across a project

## How it works

```
Wave 0:  [01] -----> integrate -> gate
                                    |
Wave 1:  [02] [03] [04] -> integrate -> gate
                                           |
Wave N:  [...] ----------> integrate -> gate -> done
```

Each wave follows a three-phase pattern:

1. **Sessions** (`for_each` at full wave concurrency) — Genie Code tasks that each complete one plan file. `edit` sessions write files within `owned_paths`; `execute` sessions run notebooks/SQL; `configure` sessions set up resources.
2. **Integrator** (single Genie Code task) — Collects session status files, runs gate checks. In `git`/`hybrid` mode: checks for stray files and commits by explicit path (the *only* committer). In `workspace` mode: status collection and gates only.
3. **Gate** (deterministic notebook) — Reads the integrator's gate JSON and every session's status file independently. Raises on failure, stopping downstream waves.

## Architecture

| Component | Path | Purpose |
|---|---|---|
| Session Runner skill | `src/skills/genie-build-session-runner/SKILL.md` | Prompt for one session: load manifest, read plan, implement within owned paths, validate, write status JSON |
| Wave Integrator skill | `src/skills/genie-build-wave-integrator/SKILL.md` | Prompt for per-wave integration: collect status, check strays, commit+push, write gate JSON |
| Gate check notebook | `src/notebooks/wave_gate_check.ipynb` | Deterministic stop: reads gate + status files, raises unless all pass |
| Placeholder notebook | `src/notebooks/genie_task_placeholder.ipynb` | Stand-in for `genie_task` (bundle CLI has no schema); fails loud if run |
| Setup notebook | `src/notebooks/setup_build_waves_job.ipynb` | Publishes skills, creates automations, dynamically generates task graph from manifest, resets jobs |
| Build job YAML | `resources/build_waves.job.yml` | Shell job (one placeholder); setup notebook replaces with full wave graph |
| Setup job YAML | `resources/setup_build_waves.job.yml` | Runs setup notebook after every deploy |
| Smoke job YAML | `resources/build_waves_smoke.job.yml` | 2-item `for_each` to verify Genie Code tasks work in job context |

## Getting started with Genie Code

Clone this repo into the same workspace where the project you want to build lives. The bundle and the project are separate Git folders — the bundle orchestrates the build, the project is what gets built.

```
/Workspace/Users/you@example.com/
  ├─ genie-build-waves/    ← this bundle (cloned once per workspace)
  └─ my-project/            ← the project being built
```

### Let Genie Code plan your build

Open Genie Code in your **project** folder and paste this prompt (replace the two paths):

> Read the build planner skill at `[/Workspace/Users/you@example.com/genie-build-waves]/src/skills/genie-build-planner/SKILL.md`, then read the files it references in that same `genie-build-waves/` directory (README, manifest schema, examples, and the two runtime skills). Once you understand the framework, analyze this project and help me decompose it into waves and sessions. The project is: **[describe what you're building]**. The genie-build-waves bundle is at `[/Workspace/Users/you@example.com/genie-build-waves]`.

Genie Code will:
1. Read the planner skill and all framework docs from the bundle repo
2. Analyze your project's files and structure
3. Propose a wave/session decomposition
4. Write the plan files, waves.json manifest, and plan index in your project
5. Configure the bundle's `databricks.yml` for your workspace and project

### Just configure the bundle

If you've already written your plans and manifest and just need the bundle configured for your workspace:

> Read `[/Workspace/Users/you@example.com/genie-build-waves]/README.md` and `[/Workspace/Users/you@example.com/genie-build-waves]/databricks.yml`. Update the `databricks.yml` target variables for my workspace. My project is at `[project workspace path]` on branch `[branch name]`. Use catalog `[catalog]` and schema `[schema]` for skills. [Create the schema automatically / I already have this schema].

### The planner skill

The full planning guide lives at `src/skills/genie-build-planner/SKILL.md` in the bundle repo. It covers:
* Project analysis and workflow mode selection
* Session decomposition rules (ownership, sizing, mode selection)
* Wave grouping and gate design
* Plan file format and conventions
* Manifest and bundle configuration

## Quick start (manual)

### 1. Prepare your project

In your target project folder (Git folder for `git`/`hybrid` mode, any workspace folder for `workspace` mode):

1. Write **session plans** as markdown files in `docs/plans/` with numbered tasks, scope, and acceptance criteria.
2. Write a **plan index** (`docs/plans/INDEX.md`) with the dependency graph and wave grouping.
3. Create a **`waves.json` manifest** — choose your workflow mode:
   * `git` (default): for code builds in a Git folder (see `examples/waves.json`)
   * `workspace`: for notebook/SQL/SDK work with no Git (see `examples/workspace-waves.json`)
   * `hybrid`: for projects that mix file editing with notebook execution
4. Create a `docs/sessions/` directory for session summaries.
5. For `git`/`hybrid` mode: add `.build-status/` to `.gitignore`.

### 2. Configure this bundle

Set variables in `databricks.yml` targets (or pass `--var` at deploy time):

```yaml
targets:
  dev:
    variables:
      project_name: "My App"
      build_root: /Workspace/Users/you@example.com/my-project/my-app
      build_branch: feature-genie-build
      manifest_path: /Workspace/Users/you@example.com/my-project/my-app/docs/plans/waves.json
      skills_catalog: my_catalog
      skills_schema: my_schema
      create_skills_schema: "true"   # set "false" if the schema already exists
```

### 3. Deploy and patch

```bash
databricks bundle deploy --target dev
# Deploy creates jobs with placeholder tasks

# Run setup to patch placeholders into real Genie Code tasks:
databricks bundle run setup_build_waves --target dev
```

### 4. Smoke test

Run setup with `run_smoke=true` to verify Genie Code tasks work inside `for_each`:

```bash
databricks bundle run setup_build_waves --target dev -p run_smoke=true
```

Pass = both iterations SUCCESS, each echoing its `session_id`.

### 5. Start the build

Run the build job from the Jobs UI. Set the `branch` parameter if not using the default. Watch each `wN_gate` task.

## When a wave fails

1. Read the `wN_gate` error and `.build-status/<run_id>/wave_<N>_gate.json`.
2. Read the failing session's status file and summary in `docs/sessions/`.
3. Passing sessions are already committed. Failing sessions' code is left uncommitted.
4. Fix the cause (plan, manifest, or code), then **Repair run** selecting `wN_sessions`, `wN_integrate` and `wN_gate`.
5. `requests` in the gate file list changes a session needed outside its owned paths. Apply them before repairing.

## Changing a build

* **Skill or prompt change**: Edit the `SKILL.md`, re-run the setup job.
* **Wave or session change**: Edit `waves.json`, re-run `bundle deploy` then the setup job. The setup notebook reads the manifest and regenerates the full task graph.
* Never edit the build jobs in the UI; deploy overwrites them.

## Workflow modes

| Mode | Sessions write to | Integrator commits | Use for |
|---|---|---|---|
| `git` (default) | Files in a Git folder | Yes, by explicit path | Code builds, app development |
| `workspace` | Notebooks, tables, dashboards, UC objects | No Git | Data engineering, ML, migrations, infra |
| `hybrid` | Mix of file edits and workspace operations | Commits file edits only | Projects combining code + execution |

Sessions also have **modes** (`edit`, `execute`, `configure`) that control what they're allowed to do. See [docs/manifest-schema.md](docs/manifest-schema.md) for details.

## Key design decisions

* **Ownership boundaries prevent conflicts** — `owned_paths` (for file work) and `owned_assets` (for resource work) don't overlap within a wave.
* **Git guardrails are conditional** — Only active in `git`/`hybrid` mode. `workspace` mode has no Git requirements at all.
* **Sessions are Git read-only** — In `git`/`hybrid` mode, only the integrator commits, by explicit path, to a feature branch.
* **Placeholder workaround** — `genie_task` isn't in the bundle CLI schema; notebook placeholders get swapped via `jobs/reset`.
* **Dynamic task graph** — The setup notebook generates the wave task structure from the manifest, so different projects with different wave counts work without YAML changes.
* **Repair-friendly** — `run_if: ALL_DONE` on integrator/gate means failures get reported. Repair re-runs only failed tasks.

## Guardrails

* In `git`/`hybrid` mode: sessions never run Git write commands; only the integrator commits.
* `main`/`master` are refused as branch targets.
* `edit` sessions touch only their `owned_paths`; `execute`/`configure` sessions touch only their `owned_assets`.
* Deploys only where `allow_deploy: true`.
* Notebook/SQL execution only where `allow_execute: true` (default for `execute`/`configure` sessions).
* `.build-status/` is never committed.

## Manifest reference

See [docs/manifest-schema.md](docs/manifest-schema.md) for the complete `waves.json` schema.
