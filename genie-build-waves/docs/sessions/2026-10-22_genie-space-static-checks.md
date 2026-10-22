# 2026-10-22: genie_space static checks (Phase 3)

Phase 3 of `docs/design/runtime-target-extensions.md`: a `genie_space` runtime target with static checks (no questions asked; questions are Phase 4). Pushed Phases 1–2 (`66f0373..bde86f9`) before starting.

## Problems and root causes

* **No timestamp in the SDK model.** `GenieSpace` has only `etag`. The raw `GET /api/2.0/genie/spaces/<id>` has `create_time` and `update_time`. On a scratch space (created, then trashed), `update_time` moved on a `serialized_space` update, a description-only update and an identical re-write, so it is a reliable "written since" signal.
* **Titles are not unique.** Two spaces in this workspace share the title "Healthcare Encounter Analytics".
* **Stale column configs are common.** 2 of 10 workspace spaces have `column_configs` for columns that no longer exist (confirmed with `DESCRIBE TABLE`). Table resolution alone would miss this.
* **Reading the configuration needs `CAN_EDIT`** (`include_serialized_space` docstring).

## Changes

* Gate (`wave_gate_check`): `_genie_space_id` (id, or a title that matches exactly one space, paged), `check_genie_space`: freshness via `update_time`, warehouse attached / exists / equal to target `warehouse_id`, tables and metric views resolve, `column_configs` columns exist, example SQL passes `EXPLAIN` (`check_example_sql`, `sql_timeout_seconds`; parameterized examples `skipped`; SQL snippets counted only). Registered in `checkers`. Header updated.
* Setup (`setup_build_waves_job`): `genie_space` in `VALID_TARGET_TYPES`; warns without `id`, validates `check_example_sql`, warns that `soak_minutes` is ignored; gate timeout +10 min per space. "probes without probe_auth" warning now only for app targets.
* Docs: manifest schema (type, `id`, freshness note, `warehouse_id`, `check_example_sql`, `sql_timeout_seconds`, gate-checks row), README, design doc (Phase 3 implemented, findings, deviation), runner skill (deploy default, wait on `update_time`, diagnose), planner skill (when and how to add a space), example wave 9.

## Verification

* Real spaces: metric-view space by name passes; 15/15 and 4/4 real example SQL pass; stale column configs and an old `update_time` fail; duplicate title, unknown id and a wrong expected warehouse fail with clear messages.
* Stubbed space: unknown schema fails; wrong measure name and unknown column fail with the planner's suggestion; parameterized example skipped.
* Setup: 5 manifest cases behave as intended. All edited cells parse; example manifest validates; `bundle validate --strict --target dev` passes.

## Decisions

* **Deviation from the design:** `id` is not required. A `name` must match exactly one space (as for dashboards), and setup warns without `id`.
* Stale `column_configs` fail the gate (the runner fixes the space definition).
* Open: the smoke capability probe does not yet check `CAN_EDIT` on the manifest's spaces.

## Files modified

`src/notebooks/wave_gate_check.ipynb`, `src/notebooks/setup_build_waves_job.ipynb`, `docs/manifest-schema.md`, `docs/design/runtime-target-extensions.md`, `README.md`, `src/skills/genie-build-session-runner/SKILL.md`, `src/skills/genie-build-planner/SKILL.md`, `examples/converge-waves.json`, `docs/sessions/INDEX.md`.
