# 2026-10-22 — Dashboard Runtime Target and validate_bundles

**Branch:** `mg-genie-build-waves-init`
**Design record:** `docs/design/runtime-target-extensions.md`

## Summary

Another Genie Code session using the framework asked for new runtime target types (`genie_space`, `dashboard`), app probes for custom agents, and a per-wave `bundle_target` override. Reviewed the request against the gate notebook, setup validation and `RuntimeTarget` schema, agreed decisions with the owner, and implemented phase 1: the `dashboard` runtime target and a structured `validate_bundles` wave field. Phases 2–4 are recorded as planned.

## Decisions

| Question | Decision |
|---|---|
| Dashboard dataset check | `EXPLAIN` by default; `execute_datasets: true` runs `SELECT * FROM (<query>) LIMIT 1` |
| Per-wave `bundle_target` | Replaced by wave `validate_bundles: [{root, target}]`; runtime targets keep their own `bundle_root`/`bundle_target` |
| Genie probe questions (phase 4) | `probe_mode: warn` by default |
| Custom agents (phase 2) | Stay `type: app`, add probes |

## Problems & Root Causes

| Problem | Root Cause |
|---|---|
| A status-only `EXPLAIN` check would pass broken dashboards | `EXPLAIN` on a query with an analysis error returns `SUCCEEDED` with `Error occurred during query planning:` as row 1 and the error as row 2 (verified with `spark.sql` and the Statement Execution API) |
| Some dashboard datasets have no SQL | Datasets can reference a table or metric view via `asset_name` (+ `catalog`/`schema`) instead of `queryLines` |
| Static validation of several bundles relied on free-text `gate` lines | No structured field; the integrator interpreted text, and the gate notebook could not check coverage |

## Changes

- **Gate notebook** (`wave_gate_check.ipynb`): `check_dashboard` (published revision after run start, warehouse set, per-dataset `EXPLAIN` or `LIMIT 1`, `asset_name` resolution via UC, single-value default parameters, multi-value/range reported `skipped`), `_run_sql` helper with timeout and cancel, `dashboard` in the checkers map. Static cell: every `validate_bundles` entry must appear in the gate file's `bundle_validations` as `pass` (roots normalized against `build_root`). Header updated.
- **Setup notebook**: `dashboard` in `VALID_TARGET_TYPES`; `validate_bundles` entries require `root` and `target`; gate timeout adds 10 min per dashboard target instead of a soak. Header updated.
- **Integrator skill**: runs `bundle validate --strict` for each `validate_bundles` entry, writes `bundle_validations` in the gate file; gate `pass` requires all of them.
- **Runner skill**: dashboard deploy default (`bundle deploy` only), wait on published revision, diagnose with `EXPLAIN` (including the SUCCEEDED-with-error gotcha), classify failing datasets as `unhealthy`.
- **manifest-schema.md**: `dashboard` type and fields (`warehouse_id`, `execute_datasets`, `dataset_timeout_seconds`), wave `validate_bundles`, runtime gate row, "Multiple bundles in one manifest" section.
- **README**: dashboard runtime gate, multi-bundle paragraph, gate notebook row.
- **examples/converge-waves.json**: `ops_dashboard` target and wave 8 with `validate_bundles` (absolute roots, since the example's `build_root` is the app folder).
- **docs/design/runtime-target-extensions.md**: decisions and phase 2–4 designs.

## Verification

- All notebook cells compile; setup `validate_manifest` passes all three examples and rejects a bad type and a `validate_bundles` entry without `target`.
- Gate static cell with fake gate files: all-pass, one missing, one failed and none-declared cases behave as expected.
- Gate notebook `check_dashboard` (executed from the notebook source) against workspace dashboards: caught a real stale column (`run_timestamp`) on the "AutoEval Results" dashboard in both modes, passed a metric-view dashboard, and resolved a dashboard by name.
- `bundle validate --strict --target dev` passes.

## Files Modified

- `src/notebooks/wave_gate_check.ipynb`
- `src/notebooks/setup_build_waves_job.ipynb`
- `src/skills/genie-build-wave-integrator/SKILL.md`
- `src/skills/genie-build-session-runner/SKILL.md`
- `docs/manifest-schema.md`
- `README.md`
- `examples/converge-waves.json`
- `docs/design/runtime-target-extensions.md` (new)
