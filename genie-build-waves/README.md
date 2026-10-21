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
Wave 0:  [01] -> integrate -> gate -> gate_check (If/else)
                                          |
                                        true
                                          |
Wave 1:  [02] [03] [04] -> integrate -> gate -> gate_check
                                                    |
                                                  true
                                                    |
Wave N:  [...] ----------> integrate -> gate -> gate_check -> done
```

Each wave follows a four-phase pattern:

1. **Sessions** (`for_each` at full wave concurrency) — Genie Code tasks that each complete one plan file. `edit` sessions write files within `owned_paths`; `execute` sessions run notebooks/SQL; `configure` sessions set up resources.
2. **Integrator** (single Genie Code task, `run_if: ALL_DONE`) — Collects session status files, runs gate checks. In `git`/`hybrid` mode: checks for stray files and commits by explicit path (the *only* committer). In `workspace` mode: status collection and gates only.
3. **Gate notebook** (`run_if: ALL_DONE`) — Reads the integrator's gate JSON and every session's status file independently. Sets a `gate_passed` task value (`true`/`false`).
4. **Gate check** (If/else condition task) — Checks `gate_passed == "true"`. If false, all downstream wave tasks are **Excluded** — zero compute on cascade failure.

## Initial builds and follow-up builds

| Phase | Waves | Sessions | Gate | Pass means |
|---|---|---|---|---|
| **Initial build** | Wide, parallel | `edit` / `execute` / `configure`, disjoint ownership | Static (validate, files, tables) | The pieces exist |
| **Follow-up (convergence)** | Sequential, one session each | `converge`: deploy, read telemetry, fix, redeploy | Static + deterministic `runtime_gate` | It deploys, runs, stays up, logs are clean |

A follow-up appends waves to the same `waves.json`. Optionally start with a parallel `edit` wave for known, file-disjoint errors; then add one `converge` wave per deployable thing, in dependency order. Each `converge` session gets `runtime_targets` (how to deploy it, where its OTel logs land, what "stable" means) and loops up to `max_attempts`. The gate notebook then checks the target itself: deployment succeeded during this run, `RUNNING`, unchanged through a soak window, no error lines for that deployment, startup markers present. **A passing stable build is part of the pass criteria.**

Deploys are single-writer: the setup job rejects any wave where a deploying session (`converge` or `allow_deploy`) shares the wave with another session. See `examples/converge-waves.json`.

## Architecture

| Component | Path | Purpose |
|---|---|---|
| Session Runner skill | `src/skills/genie-build-session-runner/SKILL.md` | Prompt for one session: load manifest, read plan, implement within owned paths, validate, write status JSON |
| Wave Integrator skill | `src/skills/genie-build-wave-integrator/SKILL.md` | Prompt for per-wave integration: collect status, check strays, commit+push, write gate JSON |
| Gate check notebook | `src/notebooks/wave_gate_check.ipynb` | Deterministic stop: reads gate + status files; for `runtime_gate` waves also checks app/job/pipeline state, soak stability and OTel error lines itself |
| Placeholder notebook | `src/notebooks/genie_task_placeholder.ipynb` | Stand-in for `genie_task` (bundle CLI has no schema); fails loud if run |
| Setup notebook | `src/notebooks/setup_build_waves_job.ipynb` | Validates the manifest, publishes skills, creates/reuses automations, generates the task graph (with per-task timeouts) from the manifest, resets jobs |
| Build job YAML | `resources/build_waves.job.yml` | Shell job (one placeholder); setup notebook replaces with full wave graph |
| Setup job YAML | `resources/setup_build_waves.job.yml` | Runs setup notebook after every deploy |
| Smoke job YAML | `resources/build_waves_smoke.job.yml` | 2-item `for_each` nonce echo plus a read-only `capability_probe` (CLI, apps/jobs read, SQL, telemetry) for converge sessions |

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
5. Deploy the bundle with `--var` flags (does not modify `databricks.yml` — the bundle stays generic)

### Deploy and run

If you've already written your plans and manifest and just need to deploy:

> Read `[/Workspace/Users/you@example.com/genie-build-waves]/README.md`. Deploy the bundle using `--var` flags — do **not** edit `databricks.yml` (keep it generic so multiple projects can share the same bundle). My project is at `[project workspace path]` on branch `[branch name]`. Use catalog `[catalog]` and schema `[schema]` for skills. [Create the schema automatically / I already have this schema].

**Important:** Always pass project-specific values as `--var` flags at deploy time. Never edit `databricks.yml` with project-specific values — the bundle is a shared tool, not a per-project config file.

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

### 2. Deploy with `--var` flags

Pass all project-specific values at deploy time. Do **not** edit `databricks.yml` — keep the bundle generic so it can be shared across projects.

```bash
databricks bundle deploy --target dev \
  --var="project_name=My App" \
  --var="instance_suffix=-my-app" \
  --var="build_root=/Workspace/Users/you@example.com/my-project" \
  --var="build_branch=feature-genie-build" \
  --var="manifest_path=/Workspace/Users/you@example.com/my-project/docs/plans/waves.json" \
  --var="skills_catalog=my_catalog" \
  --var="skills_schema=my_schema"
```

Optional variables (with defaults): `instance_suffix` (`""`), `create_skills_schema` (`"true"`), `runner_skill_id`, `integrator_skill_id`.

**One deployment per project.** `instance_suffix` is appended to the bundle root path (`.bundle/genie-build-waves<suffix>/<target>`), so each project gets its own deployment state and its own build, setup and smoke jobs. Use the same suffix every time you deploy or validate for a project. Without it, deploying for a second project replaces the first project's jobs.

### 3. Run setup to patch jobs

```bash
# Run setup to patch placeholders into real Genie Code tasks:
databricks bundle run setup_build_waves --target dev
```

### 4. Smoke test

Run setup with `run_smoke=true` to verify Genie Code tasks work inside `for_each`:

```bash
databricks bundle run setup_build_waves --target dev -p run_smoke=true
```

Pass = both iterations SUCCESS, each echoing its `session_id` and the nonce. Before a follow-up build, also read the `capability_probe` output: every check should be `ok` (and `deploy_permitted=yes`), otherwise `converge` sessions cannot work unattended.

### 5. Start the build

Run the build job from the Jobs UI. Set the `branch` parameter if not using the default. Watch each `wN_gate` task.

## When a wave fails

1. Read the `wN_gate` output, `.build-status/<run_id>/wave_<N>_gate.json` and, for convergence waves, `wave_<N>_runtime.json` (deployment id, states, error samples, missing markers).
2. Read the failing session's status file and summary in `docs/sessions/`.
3. Passing sessions are already committed. Failing sessions' code is left uncommitted.
4. Fix the cause (plan, manifest, or code), then **Repair run** selecting `wN_sessions`, `wN_integrate`, `wN_gate`, and `wN_gate_check`.
5. `requests` in the gate file list changes a session needed outside its owned paths. Apply them before repairing.

Note: downstream waves show as **Excluded** (not failed). This is the correct cascade behavior — they never ran and consumed no compute.

If the build job was redeployed and re-patched since the failed run, Jobs refuses to repair it ("job structure has changed"). Start a new run with `only` set to the failed wave's task keys and everything after it (earlier waves show as skipped).

A convergence wave can commit (its session passed) and still fail on `runtime_gate` (e.g. the app crashed during the soak). The commit is kept as progress; repair re-runs the converge session, which starts from the committed code.

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
* **Zero-compute cascade** — If/else gate checks use the Excluded propagation rule: when a gate fails, all downstream wave tasks are Excluded instantly (no wasted Genie Code compute).

## Guardrails

* In `git`/`hybrid` mode: sessions never run Git write commands; only the integrator commits.
* `main`/`master` are refused as branch targets.
* `edit` sessions touch only their `owned_paths`; `execute`/`configure` sessions touch only their `owned_assets`.
* Deploys only where `allow_deploy: true` or in `converge` sessions, only to their declared targets, and only one deploying session per wave.
* `converge` sessions must fix causes, not hide them; any suppression (test skip, compile exclude, `@ts-ignore`, swallowed errors) must be listed in the status file and is surfaced in the gate output.
* Never put the build-waves job in the bundle a `converge` session deploys — the deploy would reset the running build job.
* Notebook/SQL execution only where `allow_execute: true` (default for `execute`/`configure` sessions).
* `.build-status/` is never committed.

## Manifest reference

See [docs/manifest-schema.md](docs/manifest-schema.md) for the complete `waves.json` schema.
