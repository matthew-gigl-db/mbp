# Session Summaries — genie-build-waves

## 2026-10-22

| Session | Summary |
|---|---|
| [dashboard-target-validate-bundles](2026-10-22_dashboard-target-validate-bundles.md) | Phase 1 of runtime target extensions: `dashboard` runtime target (published in this run, every dataset passes `EXPLAIN` or `LIMIT 1` with `execute_datasets`; `EXPLAIN` errors come back as SUCCEEDED rows, so the plan text is inspected) and wave `validate_bundles` (integrator validates each bundle, gate notebook checks coverage). Phases 2–4 (app probes, `genie_space`, probe questions in `warn` mode) recorded in `docs/design/runtime-target-extensions.md`. |
| [pitch-document-polish](2026-10-22_pitch-document-polish.md) | Rebuilt hero animation as Genie Code → Lakeflow Job → Genie Code three-act narrative. Replaced columnar job view with animated Gantt-style run timeline (bars fill left-to-right, parallel iterations, attempt counting, soak window). Fixed dark-mode product logos via `<picture>` + white lockup variants. Scoped `.bp-list > li` so nested bullets no longer get numbered circles. Made deploy steps 4–5 actionable with real CLI commands. Fixed `-p` → `--params` smoke-test flag in pitch and README. |

## 2026-10-21

| Session | Summary |
|---|---|
| [retries-carryover-repair](2026-10-21_retries-carryover-repair.md) | Automatic `max_retries` on Genie Code tasks for transient `INTERNAL_ERROR: start_agent_run` (manifest `task_retries`). Integrator classifies files left by earlier runs as `carryover_files` instead of strays (summaries committed, code left for its owner, unclaimed code fails the last wave). README repair guidance with `rerun_dependent_tasks`. Converge sessions re-check the branch before each deploy. |
| [converge-mode-runtime-gate](2026-10-21_converge-mode-runtime-gate.md) | Follow-up builds: sequential `converge` sessions (deploy, read OTel logs, fix, redeploy) plus a deterministic `runtime_gate` in the gate notebook, so a passing stable build is part of the pass criteria. Manifest validation (single-writer deploys), per-task timeouts, capability probe, automation leak fix, `instance_suffix` for one deployment per project. |
| [param-placeholder-fix](2026-10-21_param-placeholder-fix.md) | Root cause: automation `user_prompt` must contain `{{param}}` placeholders for Genie Code runtime substitution. Without them, agents never see resolved parameter values. Also: nonce-based smoke test for verifying the full `{{input.*}}` → `parameters` → `{{param}}` chain. |
| [if-else-cascade-and-deploy-pattern](2026-10-21_if-else-cascade-and-deploy-pattern.md) | Replaced raise-on-failure with If/else condition tasks for zero-compute cascade. Researched all six `run_if` options. Added `outcome: "true"` for condition task dependencies. Adopted `--var` deploy pattern. Enriched `for_each` inputs with session titles. |

## Commit History (branch `mg-genie-build-waves-init`)

| # | Commit | Description |
|---|---|---|
| 1 | `775a7ab` | Initial bundle: 16 files, full architecture |
| 2 | `8a23ef7` | Schema auto-creation, SDK skill publish, automation API fixes |
| 3 | `7225bb7` | `genie_task.context` → `parameters` (Jobs API field name) |
| 4 | `25aa240` | If/else gate checks for zero-compute cascade |
| 5 | `973ed14` | Add `outcome` to If/else condition task dependency |
| 6 | (refactor) | `--var` flags instead of editing `databricks.yml` |
| 7 | (fix) | Restore example placeholders in target variables |
| 8 | (feat) | Session titles in `for_each` inputs and task descriptions |
| 9 | (feat) | Nonce-based smoke test for parameter resolution |
| 10 | (fix) | `{{param}}` placeholders in automation prompts — the real root cause |
| 11 | `7df5ade` | Lava glow on hover for hero CTA buttons |
| 12 | `7836ab9` | Lava text-shadow glow on ghost button hover |
| 13 | `12459a3` | Lava glow on hover for hero product strip logos |
| 14 | `cf23dcb` | Replace static hero wave diagram with animated Genie Code session |
| 15 | `eedc294` | Hero animation: Genie Code → Lakeflow Job → Genie Code narrative |
| 16 | `efc0ae2` | Lakeflow Job run view becomes animated run timeline |
| 17 | `b20fa0d` | White product lockups in dark mode for Why Genie Code cards |
| 18 | `9f21771` | Nested bullets in Best Practices no longer get numbered circles |
| 19 | `8fc83dc` | Deploy steps 4-5 actionable; fix `-p` → `--params` smoke-test flag |
