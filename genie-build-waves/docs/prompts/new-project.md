# New Project — Initial Build Planning Prompt

> Paste this into Genie Code in your **project** folder (not the bundle repo).
> Replace the bracketed placeholders with your project's details.

---

## Prompt

Read the build planner skill at `[/Workspace/Users/<you>/genie-build-waves]/src/skills/genie-build-planner/SKILL.md`, then read the files it references in that same `genie-build-waves/` directory (README, manifest schema, examples, and the two runtime skills). Once you understand the framework, analyze this project and help me decompose it into waves and sessions.

The project is: **[describe what you're building — app, pipeline, ML model, migration, etc.]**.

The genie-build-waves bundle is at `[/Workspace/Users/<you>/genie-build-waves]`.

The project root is at `[/Workspace/Users/<you>/<project-folder>]`.

### What to produce

1. Analyze the project's existing files, architecture, and requirements.
2. Determine the workflow mode (`git`, `workspace`, or `hybrid`).
3. Decompose the work into sessions with clear ownership boundaries and group them into dependency-ordered waves.
4. Write plan files in `docs/plans/` (one per session).
5. Write `docs/plans/INDEX.md` with the wave map and dependency graph.
6. Create `docs/plans/waves.json` (or the manifest path you choose) following the schema in `docs/manifest-schema.md`.
7. Create `docs/sessions/` for session summaries.
8. For `git`/`hybrid` mode: add `.build-status/` to `.gitignore`.
9. Deploy the genie-build-waves bundle using `--var` flags — do **not** edit `databricks.yml` (keep it generic so multiple projects can share the same bundle).

### Deploy command (fill in your values)

```bash
databricks bundle deploy --target dev \
  --var="project_name=[Project Name]" \
  --var="instance_suffix=-[project-slug]" \
  --var="build_root=[/Workspace/Users/<you>/<project-folder>]" \
  --var="build_branch=[feature-branch-name]" \
  --var="manifest_path=[/Workspace/Users/<you>/<project-folder>]/docs/plans/waves.json" \
  --var="skills_catalog=[catalog]" \
  --var="skills_schema=[schema]"
```

Use `--var="create_skills_schema=true"` if the schema doesn't exist yet (you need CREATE SCHEMA on the catalog), or `--var="create_skills_schema=false"` to use an existing schema.

### After deploy

1. Run setup to patch placeholders into real Genie Code tasks:
   ```bash
   databricks bundle run setup_build_waves --target dev
   ```
2. Smoke test (optional but recommended):
   ```bash
   databricks bundle run setup_build_waves --target dev --params run_smoke=true
   ```
3. Start the build:
   ```bash
   databricks bundle run build_waves --target dev
   ```

### Key rules

- **Ownership boundaries prevent conflicts** — `owned_paths` (file work) and `owned_assets` (resource work) must not overlap within a wave.
- **One session = one coherent deliverable** — small enough to finish in one Genie Code run (~30 min).
- **Wave 0 is foundational** — scaffold, shared config, base schema, secrets.
- **Write meaningful gate checks** — testable, concrete assertions (not "looks good").
- **Never edit `databricks.yml`** with project-specific values. Always use `--var` flags.
- **One deployment per project** — use `instance_suffix` to keep deployments separate.
- **`main`/`master` are refused** as branch targets.

---

_This prompt is generic. Adapt the placeholders for your project and workspace._
