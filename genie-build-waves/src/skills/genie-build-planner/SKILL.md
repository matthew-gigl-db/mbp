---
name: genie-build-planner
description: Plans and deploys a genie-build-waves project. Analyzes a Databricks project, decomposes it into dependency-ordered waves and sessions, writes plan files, creates the waves.json manifest, and deploys the bundle with --var flags. Use at the start of any project that will be built using the Genie Code Build Waves pattern.
---

# Build Planner

You are setting up a project to be built using the **Genie Code Build Waves** pattern — an orchestration framework that runs parallel Genie Code sessions in dependency-ordered waves. Your job: understand the project, decompose it into sessions and waves, write the plan files, create the manifest, and configure the bundle.

## Before you start

The `genie-build-waves` bundle is a separate repo cloned into the same workspace as the project being built. You need its absolute workspace path (provided in the user's prompt, or derive it from this skill file's own path).

Read these files in the bundle directory:

1. `README.md` — architecture overview, workflow modes, how the pattern works
2. `docs/manifest-schema.md` — complete `waves.json` schema reference
3. `examples/waves.json` — git-mode example (code builds)
4. `examples/workspace-waves.json` — workspace-mode example (ML pipeline)
5. `src/skills/genie-build-session-runner/SKILL.md` — what each session does at runtime
6. `src/skills/genie-build-wave-integrator/SKILL.md` — what the integrator does at runtime

You need to understand the schema to write a valid manifest. The **project** being built is a separate workspace folder from the bundle.

## Step 1: Analyze the project

Read the project's existing files, README, architecture docs, and any requirements. Answer:

1. **What is being built?** (app, pipeline, ML model, migration, infrastructure, documentation, etc.)
2. **What already exists?** (existing code, notebooks, tables, schemas, configs)
3. **What is the delivery target?** (Git repo, workspace folder, UC catalog, serving endpoint, etc.)
4. **What workflow mode fits?**
   - `git` — the output is files in a Git folder (apps, bundles, libraries)
   - `workspace` — the output is notebooks, tables, models, dashboards, or UC objects
   - `hybrid` — mix of file authoring and notebook/SQL execution
5. **What are the natural functional boundaries?** (modules, layers, data domains, components)

## Step 2: Decompose into sessions

Each session is one unit of work for one Genie Code task. Rules:

- **One session = one coherent deliverable.** A session should produce something testable in isolation (a file, a notebook, a table, a configured resource).
- **Small enough to finish in one Genie Code run** (~30 min of focused work). If a piece is too large, split it.
- **Clear ownership boundaries.** For `edit` sessions: `owned_paths` must not overlap within a wave. For `execute`/`configure` sessions: `owned_assets` should not overlap.
- **Choose the right session mode:**
  - `edit` — creates or modifies files (code, YAML, markdown)
  - `execute` — runs notebooks, SQL, or SDK scripts to produce data/artifacts
  - `configure` — sets up Databricks resources (jobs, pipelines, endpoints, permissions)

For each session, define:
- `session_id` — short unique id (e.g., `01`, `02a`)
- `title` — what it produces
- `scope` — precise description of what to do (this overrides the plan file if they disagree)
- `mode` — edit, execute, or configure
- `owned_paths` (edit mode) — file globs this session may touch
- `owned_assets` (execute/configure mode) — assets this session may create or modify
- `depends_on` — which prior sessions must complete first

## Step 3: Group into waves

Waves run sequentially. Sessions within a wave run in parallel. Rules:

- **Wave 0 should be foundational.** Scaffold, shared config, base infrastructure — things everything else depends on.
- **Sessions that depend on each other go in different waves.** A session can only depend on sessions in prior waves.
- **Sessions that can run in parallel go in the same wave.** Independent modules, separate data domains, parallel experiments.
- **Keep waves as wide as possible.** More parallelism = faster builds. Only serialize when there's a real dependency.
- **Write meaningful gate checks.** Each wave needs gates that verify the wave's output before the next wave starts. Gates should be concrete and testable:
  - Good: `bundle validate --strict --target dev passes`
  - Good: `Table catalog.schema.features has >0 rows`
  - Good: `All session status files have status: pass`
  - Bad: `Everything looks good` (not testable)

Typical wave structure:

| Wave | Purpose | Example sessions |
|---|---|---|
| 0 | Foundation | Scaffold, shared config, base schema, secrets |
| 1 | Core components | Independent modules, parallel data pipelines, model training |
| 2 | Integration | Components that depend on wave 1 outputs |
| 3 | Wiring | Jobs, pipelines, endpoints that connect everything |
| 4 | Polish | Tests, docs, monitoring, cleanup |

Not every project needs 5 waves. Use as many as the dependency graph requires.

## Step 4: Write plan files

Create a plan file for each session in `docs/plans/`. Format:

```markdown
# Session <id>: <title>

## Scope
<What this session delivers — copy from the manifest scope>

## Context
<What the session needs to know — architecture decisions, conventions, prior art>

## Tasks
1. <Specific numbered task>
2. <Specific numbered task>
...

## Acceptance Criteria
- [ ] <Testable criterion>
- [ ] <Testable criterion>

## Owned Paths / Assets
- `path/to/file.py`
- `catalog.schema.table_name`

## Dependencies
- Session <id>: <what it provides that this session needs>
```

Plan files are the session's instruction manual. Be specific: name files, tables, APIs, schemas. The session runner reads these at runtime.

## Step 5: Write the plan index

Create `docs/plans/INDEX.md`:

```markdown
# Build Plan Index

## Overview
<What is being built, workflow mode, target>

## Wave Map

### Wave 0: <name>
| Session | Title | Mode | Depends On |
|---|---|---|---|
| 01 | <title> | edit | — |

### Wave 1: <name>
| Session | Title | Mode | Depends On |
|---|---|---|---|
| 02a | <title> | execute | 01 |
| 02b | <title> | execute | 01 |

## Shared Files
<Files multiple sessions read but only one owns — list the owner>

## Cross-Session Dependencies
<Import chains, shared interfaces, data contracts between sessions>
```

## Step 6: Create the waves.json manifest

Write `waves.json` at the path specified in the bundle config (usually `docs/plans/waves.json` or `waves.json` at the project root). Follow the schema in `genie-build-waves/docs/manifest-schema.md` exactly.

Key decisions:
- Set `workflow.mode` based on your Step 1 analysis
- Set `context_files` to include any project memory, coding standards, or architecture docs
- Set `concurrency` per wave (defaults to number of sessions; lower it if sessions compete for shared resources)
- Write `gate` checks that the integrator can actually verify

## Step 7: Deploy the bundle with `--var` flags

**Do NOT edit `databricks.yml` with project-specific values.** The bundle is a shared, reusable tool — keep it generic. Instead, pass all project-specific values as `--var` flags at deploy time:

```bash
databricks bundle deploy --target dev \
  --var="project_name=<descriptive project name>" \
  --var="build_root=<absolute workspace path of the project being built>" \
  --var="build_branch=<feature branch name>" \
  --var="manifest_path=<absolute path to waves.json>" \
  --var="skills_catalog=<UC catalog for publishing skills>" \
  --var="skills_schema=<UC schema for publishing skills>"
```

This approach:
- Keeps the bundle's `databricks.yml` clean with generic placeholders
- Allows multiple projects to share the same bundle without Git changes
- Makes it clear which values are project-specific vs. bundle defaults

**Ask the user about the skills schema before proceeding:**

> The build framework publishes two UC Skills (session runner and wave integrator) to a Unity Catalog schema. You have two options:
>
> 1. **Auto-create a new schema** (default, `create_skills_schema: "true"`): The setup job will create `<catalog>.<schema>` if it doesn't exist. You need CREATE SCHEMA permission on the catalog.
> 2. **Use an existing schema** (`create_skills_schema: "false"`): Point `skills_catalog` and `skills_schema` at a schema you already have CREATE FUNCTION permission on. Add `--var="create_skills_schema=false"` to your deploy command.
>
> Which would you prefer? If you have an existing schema in mind, what's its name?

To determine the values:
- `build_root`: the project's absolute workspace path
- `skills_catalog`/`skills_schema`: use an existing catalog/schema the user has CREATE FUNCTION on, or let the setup job create one
- `build_branch`: follow the project's branch naming convention

For `workspace` mode projects, `build_branch` can be set to any non-main value (it's passed as a parameter but skipped by the runner/integrator).

## Step 8: Create support directories

```
mkdir -p docs/plans docs/sessions
```

For `git`/`hybrid` mode, ensure `.build-status/` is in `.gitignore`.

## Step 9: Verify

Validate from the `genie-build-waves/` bundle directory (not the project directory), passing the same `--var` flags:

```bash
databricks bundle validate --strict --target dev \
  --var="project_name=..." \
  --var="build_root=..." \
  --var="build_branch=..." \
  --var="manifest_path=..." \
  --var="skills_catalog=..." \
  --var="skills_schema=..."
```

Then verify the manifest is valid JSON and all plan files referenced in it exist in the **project** directory.

## Tips for good session decomposition

- **When in doubt, split.** Two small sessions are better than one large session that might fail halfway.
- **Shared files are dangerous.** If two sessions need to edit the same file, one must own it and the other must record a `request`. Or refactor so each session owns its own file.
- **Tests belong in the wave after the code.** Don't make a session both implement and exhaustively test — the testing session can read the implementation session's summary to know what to test.
- **Infrastructure first, logic second.** Schemas, tables, volumes, secrets, and service principals should be in wave 0.
- **Plan files are the contract.** If the plan file is vague, the session will improvise. Be specific about file names, function signatures, table schemas, and API contracts.
- **Context files are project memory.** Put coding standards, naming conventions, architecture decisions, and data dictionaries in `context_files` so every session inherits them.
- **Gate checks prevent cascading failures.** A strong gate in wave 1 prevents wave 2 from building on a broken foundation. Don't just check "all sessions passed" — check the actual outputs.
