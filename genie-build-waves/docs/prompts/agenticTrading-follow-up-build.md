# AgenticTrading Follow-up Build — Session Prompt

> Paste this into the AgenticTrading Genie Code session (thread `3363329896661919`).
> It tells the planner to read the updated genie-build-waves framework, decouple the
> old in-repo build-wave files, and plan follow-up waves (parallel fix + sequential
> converge) using the new converge mode.

---

## Prompt

We are continuing the AgenticTrading `trading-agent-app` build. The initial build (waves 0–4b) ran to completion — all 15 sessions passed — but the first real deploy failed. The app has 18 TypeScript compile errors and 23 unfulfilled cross-session requests. We need a follow-up build that fixes the errors, applies the requests, deploys the app, reads its OTel logs, and iterates until the app is stable.

### What changed since last session

The **genie-build-waves** framework (a separate bundle in `/Workspace/Users/matthew.giglia@databricks.com/mbp/genie-build-waves`) now supports:

- **`converge` session mode**: deploy → read deployment status and OTel logs → diagnose → fix → redeploy, in a bounded loop (up to `max_attempts`).
- **`runtime_targets`** in the manifest: declares each deployable thing (app, job, pipeline) with its bundle target, deploy commands, OTel telemetry table, error/ignore patterns, required startup markers, and stability criteria (soak minutes, max errors).
- **`runtime_gate`** on a wave: the gate notebook deterministically checks the named targets — deployment succeeded during this run, app is RUNNING, soak-stable, error lines clean for that deployment ID, startup markers present. A **passing stable build is part of the pass criteria**.
- **`instance_suffix`** variable: one genie-build-waves deployment per project.
- **`context_notes`** on a session: hand-over context from this interactive session.
- **Manifest validation**: the setup job rejects waves where a deploying session shares the wave with another session (single-writer rule). Converge waves are forced to concurrency 1.

Read these files from the genie-build-waves bundle to understand the updated schema:
1. `/Workspace/Users/matthew.giglia@databricks.com/mbp/genie-build-waves/README.md`
2. `/Workspace/Users/matthew.giglia@databricks.com/mbp/genie-build-waves/docs/manifest-schema.md`
3. `/Workspace/Users/matthew.giglia@databricks.com/mbp/genie-build-waves/examples/converge-waves.json`
4. `/Workspace/Users/matthew.giglia@databricks.com/mbp/genie-build-waves/src/skills/genie-build-planner/SKILL.md`

### Current state

- **Repo**: `agenticTrading`, branch `mg-genie-app-project-memory` (67a8a3a, pushed, clean)
- **App**: `trading-agent-app-dev`, deployment `01f1cd1ac4d5163ba895026388f7bce0` FAILED (tsc errors), app UNAVAILABLE, compute ACTIVE
- **OTel table**: `hls_fde_dev.dev_matthew_giglia_algo_trader_analytics.algo_trader_mcp_otel_logs`
- **App SPN**: `f38f0d16-c09c-493d-9b36-7a2d0f31e368`
- **MCP connection**: `trading_agent_mcp_connection` (snake_case, created in prior session)
- **Old branch**: `mg-genie-app-build` was deleted; the old manifest still references it
- **Infra**: secrets bootstrap run SUCCESS; ZeroBus SPN provisioned; 3 manual keys verified

### Known TypeScript errors (18, from OTel deployment logs)

```
server/routes/mcp/mcp-routes.ts(537,28): error TS6133: 'req' is declared but its value is never read.
server/routes/paper/paper-routes.ts(100,63): error TS2345: Argument of type 'number' is not assignable to parameter of type 'string'.
server/routes/paper/paper-routes.ts(108,71): error TS2345: Argument of type 'number' is not assignable to parameter of type 'string'.
server/services/config-service.ts(19,22): error TS2307: Cannot find module 'pg' or its corresponding type declarations.
server/services/finnhub-service.ts(82,11): error TS2322: Type 'unknown' is not assignable to type 'FinnhubArticle[]'.
server/services/marketaux-service.ts(76,11): error TS2322: Type 'unknown' is not assignable to type 'MarketauxResponse'.
server/services/monitoring-service.ts(21,8): error TS6133: 'PaperPosition' is declared but its value is never read.
server/services/paper-engine.ts(208,74): error TS2554: Expected 2 arguments, but got 3.
server/services/paper-engine.ts(210,42): error TS2554: Expected 2 arguments, but got 3.
server/services/paper-engine.ts(218,11): error TS2365: Operator '<' cannot be applied to types 'number' and 'string'.
server/services/paper-engine.ts(218,46): error TS18047: 'reserveFloor' is possibly 'null'.
server/services/paper-engine.ts(233,30): error TS2365: Operator '>' cannot be applied to types 'number' and 'string'.
server/services/paper-engine.ts(233,71): error TS18047: 'maxConcentrationPct' is possibly 'null'.
server/services/paper-engine.ts(416,35): error TS2554: Expected 2 arguments, but got 3.
server/services/paper-engine.ts(611,27): error TS2345: Argument of type 'Record<string, unknown>' is not assignable to parameter of type 'string'.
server/services/quote-service.ts(60,11): error TS2322: Type 'unknown' is not assignable to type 'FinnhubQuote'.
```

Note: these errors have severity `UNKNOWN` in OTel (not `ERROR`), so the gate checks body text with regex `error TS\d+`.

### Unfulfilled cross-session requests (23)

From `.build-status/489528833209375/wave_*_gate.json`:

**Wave 1:**
- `03` → delete superseded `.gitkeep` reservation files for migrations 001-009
- `09a` → delete `client/src/pages/lakebase/LakebasePage.tsx` (dead code)
- `11a` → add `!.env.example` exclusion to `.gitignore` (`.env*` blocks it)

**Wave 2:**
- `05` → `server/migrations/migrate.ts`: add imports for migration006 + migration007
- `05` → `algo_trader_credentials` secret scope: create `ROBINHOOD_TOKEN_ENCRYPTION_KEY`
- `05` → `app.yaml`: add `ROBINHOOD_TOKEN_ENCRYPTION_KEY` env var
- `06a` → `server/server.ts`: add `startPollers(appkit.lakebase)` call in section 4
- `13` → `server/migrations/migrate.ts`: add imports for migration008 + migration009
- `13` → `databricks.yml`: add per-target overrides for catalog, config_schema, lakebase_branch, lakebase_project_id
- `13` → `app.yaml`: add `SYNCED_TABLE_SCHEMA` env var
- `13` → `scripts/deploy.sh`: add phases 2b-2d (resolve config_schema, run setup_lakebase_cdf, redeploy)

**Wave 3:**
- `08` → `server/routes/health-routes.ts`: add mcpProxy to healthState and HealthResponse
- `08` → `server/server.ts`: add `closeRobinhoodClient()` to shutdown handler
- `08` → `server/services/quote-service.ts`: wire primary quote source to `callRobinhoodTool`
- `06b` → `server/server.ts`: add `startMonitoring(appkit.lakebase)` and `stopMonitoring()` in SIGTERM
- `09b` → `server/routes/paper/paper-routes.ts`: add `GET /api/config` route
- `09b` → `server/routes/health-routes.ts`: add per-stream last_update timestamps
- `09b` → delete `client/src/pages/ConnectPlaceholder.tsx` (dead code)
- `09b` → delete `client/src/pages/lakebase/LakebasePage.tsx` (dead code; also requested by 09a)

**Wave 4a:**
- `10` → `databricks.yml`: add `trading-agent-mcp` to app resources block with CAN_QUERY
- `10` → `databricks.yml`: add per-target override for `mcp_execute_principal`
- `10` → `app.yaml`: ensure `SYNCED_TABLE_SCHEMA` env var present

### Step 1: Decouple old in-repo build-wave files

The trading-agent-app bundle still includes old in-repo copies of the build-wave jobs:

```
databricks.yml line 11:  - docs/plans/genie-prompts/*.job.yml
```

This is dangerous: deploying the app would reset the build job managed by genie-build-waves. **Before writing the new manifest:**

1. Remove the `- docs/plans/genie-prompts/*.job.yml` include line from `trading-agent-app/databricks.yml`.
2. Delete the three `.job.yml` files from `docs/plans/genie-prompts/` (build_waves.job.yml, setup_build_waves.job.yml, build_waves_smoke.job.yml).
3. Delete the old in-repo notebooks: `docs/plans/genie-prompts/wave_gate_check`, `docs/plans/genie-prompts/setup_build_waves_job`, `docs/plans/genie-prompts/genie_task_placeholder`.
4. Delete the old in-repo skills folder: `docs/plans/genie-prompts/skills/`.
5. Keep `docs/plans/genie-prompts/waves.json` (the manifest) and `docs/plans/genie-prompts/README.md` — those stay in the project.
6. Run `bundle validate --strict --target dev` to confirm the app bundle is clean.

### Step 2: Write the follow-up manifest

Rewrite `docs/plans/genie-prompts/waves.json` as a **follow-up build**. Keep the first 6 lines of metadata (repo_root, bundle_root, etc.) but update:

- `branch`: `mg-genie-app-project-memory` (the current branch; `mg-genie-app-build` was deleted)
- Remove the old `skills` block (the build now uses the shared genie-build-waves skills, not in-repo copies)
- Add `context_files`: `["PROJECT_MEMORY.md", "docs/plans/INDEX.md"]`
- Add `runtime_targets` with one target `app`:
  ```json
  "runtime_targets": {
    "app": {
      "type": "app",
      "name": "trading-agent-app-dev",
      "resource_key": "trading_agent_app",
      "bundle_root": "/Workspace/Users/matthew.giglia@databricks.com/agenticTrading/trading-agent-app",
      "bundle_target": "dev",
      "deploy_commands": [
        "bundle deploy --target dev",
        "bundle run trading_agent_app --target dev"
      ],
      "telemetry": {
        "logs_table": "hls_fde_dev.dev_matthew_giglia_algo_trader_analytics.algo_trader_mcp_otel_logs",
        "deployment_id_attribute": "app.deployment_id",
        "log_source_attribute": "app.log_source",
        "error_patterns": ["error TS\\d+", "ELIFECYCLE", "Error building app", "Unhandled", "FATAL", "Cannot find module"],
        "ignore_patterns": ["Updated file:", "Skipping query type generation"],
        "required_markers": ["listening on"]
      },
      "stability": { "soak_minutes": 10, "max_errors": 0 }
    }
  }
  ```

**Waves** — keep waves 0-4b as-is (they already ran, their results are in `.build-status/489528833209375/`), and **append** new waves:

#### Wave 5 — parallel edit: fix compile errors and apply cross-session requests

The 18 tsc errors and 23 requests touch disjoint file groups. Split into 3-4 parallel edit sessions with non-overlapping `owned_paths`. Suggested grouping (adjust if you find better boundaries):

- **Session 14**: paper-engine.ts (7 errors: TS2554, TS2365, TS18047, TS2345) + paper-routes.ts (2 errors: TS2345) + requests targeting paper routes
- **Session 15**: external API services — finnhub-service.ts (TS2322), marketaux-service.ts (TS2322), quote-service.ts (TS2322), config-service.ts (TS2307 `pg` module) + monitoring-service.ts (TS6133) + requests targeting those files
- **Session 16**: server.ts lifecycle wiring (requests from 06a, 06b, 08: startPollers, startMonitoring, closeRobinhoodClient, shutdown) + health-routes.ts (requests from 08, 09b) + mcp-routes.ts (TS6133 unused `req`) + migrate.ts (requests from 05, 13 to register migrations 006-009)
- **Session 17**: config/infra cleanup — databricks.yml changes (requests from 10, 13), app.yaml env vars (requests from 05, 13, 10), .gitignore fix (request from 11a), dead code deletion (ConnectPlaceholder, LakebasePage, .gitkeep stubs), .env.example, deploy.sh phases (request from 13)

Static gate only (bundle validate, no runtime_gate). Each session's plan file should include a `## Known issues` section listing the specific errors and requests it handles, with their source.

#### Wave 6 — converge: deploy and stabilize the app

One `converge` session (e.g. session 18), alone in its wave:
- `mode`: `converge`
- `runtime_targets`: `["app"]`
- `owned_paths`: broad — `server/**`, `client/**`, `shared/**`, `package.json`, `pnpm-lock.yaml`, `tsconfig*.json`, `app.yaml`, `resources/**`
- `max_attempts`: 6
- `timeout_minutes`: 180
- `depends_on`: all wave 5 sessions
- Wave has `runtime_gate: ["app"]`
- Scope: deploy the app, read OTel logs for the new deployment ID, diagnose errors, fix within owned_paths, and repeat until the app is RUNNING with no error lines and the `listening on` marker present in OTel logs.

#### Wave 7 (optional, may defer) — configure: MCP connection + MCP service

This requires the app to be running stably first. If the MCP service registration (`trading_agent_mcp_connection`) needs the app's SPN secret keys or infra changes, list those as `manual_prereqs`. Mode `configure` with `allow_deploy: true`.

### Step 3: Write plan files

Create `docs/plans/<session_id>_<title>.md` for each new session (14-18+). Use the template from the planner skill. Each plan should include:
- `## Known issues` — the specific errors and requests this session handles, with their OTel deployment ID or gate file source
- `## Tasks` — numbered, specific tasks
- `## Context` — cross-session dependencies, prior session summaries in `docs/sessions/`

When you write `context_notes` on a session in the manifest, include findings from this conversation that the runner should know but shouldn't have to re-derive.

### Constraints

- **Stay on branch `mg-genie-app-project-memory`**. The old `mg-genie-app-build` branch was deleted.
- **Do NOT deploy the app from this session.** The converge session will handle deployment. This session only writes plans and the manifest.
- The genie-build-waves bundle will be deployed separately with `--var="instance_suffix=-agentic-trading"` to get its own build/setup/smoke jobs.
- **No suppressions**: fix the actual errors. No `@ts-ignore`, no `tsconfig` `exclude`, no swallowed exceptions.
- **Single-writer rule**: any wave with a `converge` session must have exactly that one session and concurrency 1.
- **pnpm-lock.yaml**: the lock file exists but was not maintained by the initial build. If a converge session adds a dependency (e.g. `@types/pg` for TS2307), it must run `pnpm install` and commit the updated lock file.

### Deliverables

Before committing, show me:
1. The diff for `databricks.yml` (include line removal confirmed)
2. The list of files being deleted from `docs/plans/genie-prompts/`
3. The full `waves.json` with old waves preserved and new waves appended
4. The plan files for each new session
5. `bundle validate --strict --target dev` passing

Then commit and push on `mg-genie-app-project-memory`.

---

_This prompt was generated from the genie-build-waves session on 2026-10-21._
