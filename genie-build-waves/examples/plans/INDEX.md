# Example Build Plans — Session Index

**Bundle:** `my-app`
**Created:** 2026-10-21

---

## Session Order

| # | Session | Produces | Depends On | Est. Effort |
|---|---------|----------|------------|-------------|
| 01 | [Bundle Scaffold](01_bundle_scaffold.md) | Fixed `databricks.yml`, directory tree | Nothing | Light |
| 02 | [Data Model](02_data_model.md) | DDL notebook with target tables | 01 | Medium |
| 03 | [Pipeline Code](03_pipeline.md) | SDP pipeline notebook + resource YAML | 01 | Medium |
| 04 | [Job Configuration](04_jobs.md) | Orchestration job YAML | 01 | Light |

---

## Build Waves

### Wave 0 — Foundation (serial)

| Session | Notes |
|---|---|
| **01 Bundle Scaffold** | Creates all shared structure. Must pass before parallel work. |

**Gate:** `bundle validate --strict --target dev` passes.

### Wave 1 — Parallel Foundations (3 concurrent)

| Session | Owns |
|---|---|
| **02 Data Model** | `src/notebooks/target_tables_ddl.*` |
| **03 Pipeline Code** | `src/pipelines/**`, `resources/pipeline.pipeline.yml` |
| **04 Job Configuration** | `resources/orchestration.job.yml` |

**Gate:** All sessions pass. `bundle validate --strict --target dev` passes.
