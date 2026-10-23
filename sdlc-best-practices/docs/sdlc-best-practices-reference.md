# SDLC Best Practices on Databricks with Declarative Automation Bundles

**Author:** Matthew Giglia | Databricks Field Engineering  
**Version:** 1.0 | October 2026  
**Validated with:** Databricks CLI 1.22.1 (direct deployment engine), AWS, serverless compute

---

## Overview

This reference goes one level deeper than the two documents it builds on:

| Document | What it decides |
|---|---|
| [Enterprise Workspace Architecture](../../workspace-architecture/docs/document.md) | Which workspaces, catalogs, identities, and networks exist (Section 12 introduces CI/CD) |
| [UC Naming Convention](../../developer-user-isolation-in-uc/docs/uc-naming-convention-reference.md) | How catalogs and schemas are named per environment, and the zero-hardcoding rule |
| **This document** | How code moves from a developer's laptop to production safely, repeatably, and auditably -- with Declarative Automation Bundles and GitHub Actions |

Everything here is demonstrated by working examples in [`../examples`](../examples):

* [`orders_bundle/`](../examples/orders_bundle) -- a complete bundle: UC schema, volume, grants, a serverless Lakeflow Spark Declarative Pipeline, a job with a data quality gate, unit tests, and five targets (`dev`, `ci`, `tst`, `uat`, `prod`).
* [`github-actions/`](../examples/github-actions) -- CI, CD, PR cleanup, and a reusable deploy workflow using workload identity federation.
* [`comparison/`](../examples/comparison) -- the same deployment written against the REST API and with Terraform, analyzed in [Deployment Complexity Comparison](deployment-complexity-comparison.md).

Declarative Automation Bundles were formerly called Databricks Asset Bundles (DABs). The CLI commands (`databricks bundle ...`) and file format are unchanged.

---

## 1. The Lifecycle at a Glance

```
  feature branch                 pull request                  main                        release
 ┌──────────────┐  push   ┌───────────────────────┐ merge ┌──────────────┐  approve  ┌──────────────┐
 │ dev target   │ ──────▶ │ ci target (per PR)    │ ────▶ │ tst  ──▶ uat │ ────────▶ │ prod         │
 │ mode: dev    │         │ lint + unit tests     │       │ integration  │  plan +   │ apply the    │
 │ personal     │         │ validate --strict     │       │ test + data  │  review   │ approved     │
 │ schema       │         │ deploy + validate-only│       │ quality gate │           │ plan; tag    │
 └──────────────┘         │ destroyed on close    │       └──────────────┘           └──────────────┘
   human identity         └───────────────────────┘        service principals only (OIDC, no secrets)
```

Three rules hold the picture together:

1. **One definition, many environments.** The same bundle files deploy to every target. Only the `targets` block differs.
2. **Humans deploy to dev; service principals deploy everything else.** Shared environments are changed only by CI/CD.
3. **Promote a commit, not a rebuild.** The commit that passed `tst` is the commit that reaches `prod`, and production applies a plan a reviewer has read.

---

## 2. Principles

| # | Principle | How it shows up in the example |
|---|---|---|
| 1 | **Everything is code** -- pipelines, jobs, schemas, grants, permissions, schedules | `orders_bundle/` contains no click-ops prerequisites except the catalog and identities |
| 2 | **The catalog is the environment** | `catalog: retail_dev / retail_tst / retail_uat / retail` per target; schema names identical from `tst` onward |
| 3 | **Zero hardcoding in resources** | Resource files reference `${var.*}` and `${resources.*}` only; literals live in `targets` |
| 4 | **One resource file per deployable asset** | `resources/<type>/<name>.<type>.yml` |
| 5 | **Reference resources, not names** | `${resources.schemas.orders_schema.name}`, `${resources.pipelines.orders_medallion.id}` |
| 6 | **Separate deploy and run identities** | Deploy SP from `DATABRICKS_CLIENT_ID`; workloads `run_as` a different SP |
| 7 | **No long-lived secrets in CI** | GitHub OIDC workload identity federation (`DATABRICKS_AUTH_TYPE: github-oidc`) |
| 8 | **Validate, plan, then apply** | `bundle validate --strict` on every run; `bundle plan` reviewed before `prod` |
| 9 | **Protect data from deploys** | `lifecycle.prevent_destroy: true` on the prod schema and volume |
| 10 | **Ephemeral environments are cleaned up automatically** | `pr-cleanup.yml` destroys the `ci` target when a PR closes |
| 11 | **Pin versions** | `databricks_cli_version` in the bundle, CLI version in CI, actions pinned to commit SHAs |
| 12 | **Test logic without Spark, test pipelines with data** | Pure-Python rules + pytest; fixture-seeded integration run in `tst` |

---

## 3. Repository and Bundle Layout

Databricks recommends a single repository holding both code and bundle configuration, with trunk-based development so `main` is always deployable.

```
orders_bundle/
├── databricks.yml                  # bundle, variables, artifacts, targets -- the ONLY place for env values
├── pyproject.toml                  # the bundle's own Python package (orders_lib) + test config
├── resources/
│   ├── schemas/orders.schema.yml
│   ├── volumes/landing.volume.yml
│   ├── pipelines/orders_medallion.pipeline.yml
│   └── jobs/orders_refresh.job.yml
├── src/
│   ├── orders_lib/                 # business rules + quality gate (wheel entry point)
│   └── pipelines/orders_medallion/transformations/   # bronze / silver / gold
├── scripts/make_fixture_orders.py  # integration test data
└── tests/test_rules.py
```

**When to split into multiple bundles.** One bundle is one unit of deployment and ownership. Split when parts have different owners, different release cadences, or different blast radius. The common split is *infra* (schemas, volumes, warehouses, secret scopes, Lakebase; deployed rarely, `prevent_destroy` everywhere) and *app* (jobs, pipelines, apps, dashboards; deployed often). Deploy infra first; keep catalog and schema variables identical per target across both.

**Monorepo with several bundles.** Give each bundle its own folder, its own workflow `paths:` filter, and its own GitHub environments or concurrency group, so a change to one data product never redeploys another.

---

## 4. Declarative Automation Bundles -- Deep Dive

### 4.1 What `bundle deploy` actually does

A single `databricks bundle deploy -t <target>` performs, in order:

1. **Load and merge** `databricks.yml`, every `include`d file, and the selected target's overrides.
2. **Resolve** variables (`--var`, `BUNDLE_VAR_*`, target values, defaults, lookups) and substitutions.
3. **Apply mode and presets** -- name prefixes, tags, paused triggers, development pipelines.
4. **Validate** the result against the bundle schema and mode rules.
5. **Build artifacts** (here: `uv build --wheel`) and upload them.
6. **Sync files** to `workspace.file_path`, honoring `.gitignore`, deleting files you removed.
7. **Acquire the deployment lock** so two deploys of the same target cannot interleave.
8. **Plan** creates, updates, and deletes by comparing config with the last deployment snapshot and the live workspace.
9. **Apply** in dependency order derived from `${resources.*}` references.
10. **Record state** in the workspace and release the lock.

Each of these is a component you would otherwise build and maintain yourself. See [Deployment Complexity Comparison](deployment-complexity-comparison.md).

### 4.2 The direct deployment engine

The direct engine is the default for new bundles since CLI 1.3.0, and the Terraform engine was removed in CLI 1.20.0. Set it explicitly so intent is visible:

```yaml
bundle:
  name: orders_bundle
  engine: direct
  databricks_cli_version: ">= 1.20.0, < 2.0.0"
```

What it gives you for SDLC purposes:

* **No Terraform state or provider download** -- no backend bucket, no registry access through proxies.
* **Faster deploys** (up to 40% per Databricks documentation).
* **Field-level plans** -- `bundle plan -o json` explains which field triggered each action.
* **Replayable plans** -- `bundle deploy --plan plan.json` applies exactly a reviewed plan.
* **Broader resource coverage** -- catalogs, external locations, Genie spaces, Lakebase, and more.
* **Immutable folders** (optional) -- deploy to a content-addressed, read-only folder for tamper protection.

Because the engine compares config with the last deployment snapshot, a change in `databricks.yml` always produces an update. Out-of-band UI edits to a bundle-managed job are overwritten on the next deploy -- which is the point.

### 4.3 Targets and deployment modes

| Behavior | `mode: development` | `mode: production` | No mode + presets (`ci`) |
|---|---|---|---|
| Resource name prefix | `[dev <short_name>] ` | none | `presets.name_prefix` |
| UC schema prefix | `dev_<short_name>_` | none | derived from `name_prefix` |
| Schedules and triggers | paused | as configured | `presets.trigger_pause_status` |
| Pipelines | `development: true` | validated `development: false` | `presets.pipelines_development` |
| Concurrent job runs | enabled | as configured | `presets.jobs_max_concurrent_runs` |
| Deployment lock | disabled | enabled | enabled |
| Git branch check | no | yes, if `git.branch` set (`--force` overrides) | no |
| User paths / `run_as` / `permissions` | anything goes | validated unless deploying as a service principal | anything goes |

Precedence is: **resource setting > preset > mode default**. That is why `orders_refresh.job.yml` does *not* set `schedule.pause_status` -- the target's `trigger_pause_status` decides it (paused everywhere except `prod`).

The example uses five targets:

| Target | Who deploys | Mode | Catalog | Schema | Purpose |
|---|---|---|---|---|---|
| `dev` | each developer | development | `retail_dev` | `dev_<user>_orders` | iterate from a feature branch |
| `ci` | CI service principal | presets only | `retail_dev` | `pr<N>orders` | isolated per-PR environment |
| `tst` | tst service principal | production | `retail_tst` | `orders` | integration tests on merge |
| `uat` | uat service principal | production | `retail_uat` | `orders` | business validation |
| `prod` | prod service principal | production | `retail` | `orders` | the real thing |

### 4.4 Presets

Presets are named switches applied to every resource in a target. The useful ones:

| Preset | Typical use |
|---|---|
| `name_prefix` | Per-PR or per-feature isolation without development mode |
| `trigger_pause_status` | `PAUSED` everywhere except prod |
| `pipelines_development` | Cheaper, faster pipeline clusters in non-prod |
| `jobs_max_concurrent_runs` | Raise in dev, keep at 1 in prod |
| `tags` | FinOps and ownership tags on every taggable resource |
| `artifacts_dynamic_version` | Unique wheel version per deploy so serverless picks up changed code |
| `source_linked_deployment` | Dev only: run directly from workspace Git folder sources |

### 4.5 Variables, substitutions, and lookups

* Declare every variable with a `description` in `databricks.yml`; set environment values in `targets.<t>.variables`.
* Override at deploy time with `--var="name=value"` or `BUNDLE_VAR_name` environment variables -- the CI pattern used for `run_as_service_principal` and `pr_number`.
* Variables can reference substitutions and other variables (`workload_principal` defaults to `${workspace.current_user.userName}` and is set to `${var.run_as_service_principal}` in shared targets).
* Use **lookups** for IDs that differ per workspace: `lookup: { warehouse: "Shared Serverless" }`, also for `cluster_policy`, `service_principal`, `job`, `pipeline`, and others. Never paste IDs.
* Use `type: complex` for structured values such as a shared cluster spec.

Common substitutions: `${bundle.name}`, `${bundle.target}`, `${workspace.current_user.userName}`, `${workspace.current_user.short_name}`, `${workspace.file_path}`, `${resources.<type>.<key>.<field>}`.

### 4.6 Resource references and dependency ordering

Referencing another resource -- not its name -- does three things: it orders creation (schema before volume before pipeline before job), it carries mode prefixes through automatically (the dev job's `schema` parameter becomes `dev_<user>_orders` without any code), and it threads generated IDs (the pipeline ID into the job's `pipeline_task`).

```yaml
# resources/jobs/orders_refresh.job.yml
parameters:
  - name: schema
    default: ${resources.schemas.orders_schema.name}
tasks:
  - task_key: refresh_pipeline
    pipeline_task:
      pipeline_id: ${resources.pipelines.orders_medallion.id}
```

Use `${var.schema_name}` only inside the schema resource itself.

### 4.7 Identity: deployers, run-as, and permissions

Follow the Databricks recommendation of **separate service principals for deployment and runtime**:

| Identity | Configured by | Needs |
|---|---|---|
| Deploy SP (one per shared environment) | GitHub environment variable `DATABRICKS_CLIENT_ID` + federation policy | Workspace access; `USE CATALOG` + `CREATE SCHEMA` on the target catalog; *Service principal: User* role on the run-as SP |
| Run-as SP | `run_as.service_principal_name` | `USE CATALOG` on the catalog; schema privileges granted by the bundle (`workload_principal`) |
| Humans | account groups | `CAN_VIEW` / `CAN_RUN` on shared environments, never `CAN_MANAGE` |

The example's shared targets declare the deployer explicitly:

```yaml
permissions:
  - service_principal_name: ${workspace.current_user.userName}   # the deploying SP's application ID
    level: CAN_MANAGE
  - group_name: ${var.engineers_group}
    level: CAN_VIEW
  - group_name: ${var.operators_group}
    level: CAN_RUN
```

This does two jobs. It satisfies `bundle validate --strict`, which otherwise warns that the deployment folder carries permissions not configured in the bundle. And it acts as a guard: when a human tries to deploy a shared target, their email is not a service principal, so `--strict` validation fails and the permission assignment cannot succeed. Shared environments are changed through CI/CD only.

Rules of thumb:

* Top-level (or target-level) `permissions` apply to every supported resource and translate levels per type (`CAN_RUN` becomes `CAN_MANAGE_RUN` on jobs).
* The same identity must not appear in both bundle-level and resource-level `permissions`.
* Identify service principals by application ID in `run_as`, `permissions`, and UC `grants`.
* Deploy to a path owned by the deploying identity (the default under its home folder) or a team-owned folder -- not `/Workspace/Shared/`.

### 4.8 Protecting data

```yaml
targets:
  prod:
    resources:
      schemas:
        orders_schema:
          lifecycle:
            prevent_destroy: true
      volumes:
        landing_volume:
          lifecycle:
            prevent_destroy: true
```

With `prevent_destroy`, neither `bundle destroy` nor accidentally deleting the resource block can drop production data. Unlike Terraform, the setting can be applied per target, so dev and ci stay disposable.

### 4.9 Shared code and artifacts

The example keeps business rules in a real Python package (`src/orders_lib`) used three ways:

| Consumer | How it gets the code |
|---|---|
| Unit tests (CI runner) | `pythonpath = ["src"]` in `pyproject.toml` |
| Pipeline (serverless) | `environment.dependencies: ["--editable ${workspace.file_path}"]` |
| Job quality gate (serverless) | wheel built by `artifacts:` and attached as `../../dist/*.whl`; `python_wheel_task` entry point |

One definition of the silver expectations (`SILVER_EXPECTATIONS`) is enforced in the pipeline and asserted in tests, so the rule tested is the rule run.

### 4.10 Plans and approved changes

```bash
databricks bundle plan -t prod                    # human-readable diff
databricks bundle plan -t prod -o json > plan.json
databricks bundle deploy -t prod --plan plan.json --auto-approve --fail-on-active-runs
```

In `cd.yml`, the `plan-prod` job publishes the plan to the job summary and uploads `plan.json`. The `prod` job waits for an environment reviewer, downloads that exact file, and applies it. `--fail-on-active-runs` refuses to deploy over a running job or pipeline.

### 4.11 Adopting existing resources

Teams rarely start from zero. To bring UI-built jobs and pipelines under bundle control without duplicates:

```bash
databricks bundle generate job --existing-job-id <dev_job_id> -t dev    # writes resource YAML + downloads sources
databricks bundle deployment bind my_job <dev_job_id> -t dev
databricks bundle deployment bind my_job <prod_job_id> -t prod
```

After binding, the next deploy updates the existing object in place.

### 4.12 Python configuration and mutators

Bundles can also be defined in Python (`databricks-bundles` package). The highest-value use is **mutators** -- functions applied to every job or pipeline at deploy time -- for cross-cutting policy such as default notifications, required tags, or blocking classic compute. Keep resource definitions in YAML for readability; add Python where you would otherwise copy-paste.

### 4.13 Templates

Start new projects from `databricks bundle init` (`default-python`, `default-sql`, `dbt-sql`, `mlops-stacks`, `pydabs`, and others) or publish an organization template with `databricks_template_schema.json` so every team starts with the same targets, tags, and CI wiring.

### 4.14 Gotchas found while building the example

| Observation (CLI 1.22.1) | Implication |
|---|---|
| `bundle validate -o json` shows `${resources.*}` references unresolved for fields that depend on other resources | Read resolved values (catalog, schema name) from the schema resource's own fields, as `_deploy.yml` does |
| With `presets.name_prefix: pr42_`, resources become `pr42_orders_medallion` but the UC schema becomes `pr42orders` (trailing separator dropped) | Expect the schema form in queries and cleanup scripts; development mode produces `dev_<user>_orders` as documented |
| `--strict` fails on "workspace folder has permissions not configured in bundle" when the deployer is not declared | Declare the deploying identity with `CAN_MANAGE` per shared target |
| `sync.exclude` patterns that match nothing are warnings, so `--strict` fails | Rely on `.gitignore` for build outputs instead of an exclude list |
| Notebook paths must match the on-disk extension; `.sql` notebooks need a SQL warehouse task | Validate every change with `bundle validate --strict` |

---

## 5. Testing Strategy

| Layer | Runs where | Catches | In the example |
|---|---|---|---|
| Lint + unit tests | GitHub runner, no workspace | logic errors, broken rules | `ruff`, `pytest tests/` (no Spark needed) |
| Static bundle validation | GitHub runner + workspace API | bad YAML, missing paths, wrong references, permission gaps | `bundle validate --strict` |
| Ephemeral deploy | `ci` target in dev workspace | permission and dependency errors, pipeline graph errors | `bundle deploy -t ci` + `bundle run orders_medallion --validate-only` |
| Integration test | `tst` target | end-to-end behavior on realistic data | fixture upload + `bundle run orders_refresh` |
| Data quality gate | every scheduled run, every environment | bad data reaching consumers | `quality_gate` task fails the job |
| Expectations | inside the pipeline | bad rows | `expect_all_or_drop(SILVER_EXPECTATIONS)` |

Keep Spark out of unit-tested modules where possible. When DataFrame tests are needed, run them with Databricks Connect against serverless or with a local Spark session, and compare with a DataFrame equality helper such as `chispa`.

---

## 6. Promotion, Release, and Rollback

* **Promotion** -- `cd.yml` runs `tst -> uat -> plan-prod -> prod` on one commit. Environments are gated by GitHub environment protection rules, not by branches.
* **Release tags** -- after `prod`, the workflow tags the deployed commit (`orders-prod-<date>-<run>`). Tags are the rollback catalog.
* **Rollback** -- run `cd` manually with `ref` set to the last good tag. The same validation, plan, and approval path applies. Data changes are not rolled back by redeploying code; use Delta time travel or restore for data.
* **Hotfix** -- branch from `main`, PR, merge. Avoid long-lived release branches unless regulation requires them; when it does, set `git.branch` on the production target so production mode enforces it.
* **Do not** run `bundle destroy` on shared targets. The reusable workflow refuses to destroy anything but `ci`.

---

## 7. CI/CD with GitHub Actions (summary)

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | pull request to `main` | lint, unit tests, wheel build; deploy `ci` target for the PR; validate pipeline graph |
| `pr-cleanup.yml` | pull request closed | destroy the PR's `ci` deployment |
| `cd.yml` | push to `main`, manual dispatch | unit tests; deploy + integration test `tst`; deploy `uat`; plan prod; approved apply; tag |
| `_deploy.yml` | `workflow_call` | the one implementation of validate / plan / deploy / destroy |

Hardening applied: OIDC federation (no Databricks secrets), `permissions:` least privilege per job, actions pinned to full commit SHAs, pinned CLI version, `concurrency` groups that never cancel an in-flight deploy, fork PRs excluded from deploy jobs, required reviewers on `prod`.

Step-by-step setup: [GitHub Actions Setup Guide](github-actions-setup.md).

---

## 8. Choosing the Right Tool

| Concern | Declarative Automation Bundles | Terraform | REST API / SDK scripts |
|---|---|---|---|
| Account and cloud infrastructure (workspaces, networking, metastores, storage credentials) | no | **yes** | no |
| Catalogs, external locations, identity, admin-level policies | possible | **yes** (platform team) | no |
| Schemas, volumes, grants owned by a data product | **yes** | possible | avoid |
| Jobs, pipelines, apps, dashboards, model serving, Genie spaces | **yes** | possible, heavier | avoid |
| Code sync and artifacts | **built in** | manual | manual |
| Per-developer and per-PR environments | **built in** | separate state per copy | manual |
| One-off automation, custom tooling, operational tasks | `bundle run` | no | **yes** |

The layered model: **Terraform owns the platform** (accounts, workspaces, networking, catalogs, identities); **bundles own the workloads** each team ships. The handoff is a catalog plus the service principals and grants a bundle needs. Details and measured examples: [Deployment Complexity Comparison](deployment-complexity-comparison.md).

---

## 9. Operating the Lifecycle

* **Drift** -- schedule `bundle plan -t prod` (read-only) and alert when the plan is non-empty; someone changed production outside CI/CD.
* **Cost and ownership** -- `presets.tags` puts `project`, `businessUnit`, `costCenter`, `owner`, and `env` on every taggable resource; query `system.billing.usage` by tag.
* **Stale dev deployments** -- dev-mode resources carry a `dev` tag with the developer's name; review them periodically and ask owners to `bundle destroy -t dev`.
* **CLI upgrades** -- bump the pinned CLI version in a PR; `ci` proves it before `main` uses it.
* **Auditing** -- the GitHub deployment history plus `system.access.audit` (actions by the deploy SP) give a complete who-changed-what trail.

---

## 10. Checklist

* [ ] `bundle.engine: direct` and a `databricks_cli_version` range
* [ ] No catalog, schema, host, ID, or principal literals outside `targets`
* [ ] One resource file per asset; schema referenced via `${resources.schemas.*}`
* [ ] `dev` uses `mode: development`; shared targets use `mode: production` with `run_as`
* [ ] Separate deploy and run-as service principals per shared environment
* [ ] Shared targets declare the deployer `CAN_MANAGE`; humans get `CAN_VIEW` / `CAN_RUN`
* [ ] `prevent_destroy` on production schemas, volumes, and other data-bearing resources
* [ ] Schedules paused outside prod via `trigger_pause_status`
* [ ] Unit tests and `bundle validate --strict` required on every PR
* [ ] Per-PR environment created and destroyed automatically
* [ ] Integration test plus data quality gate in `tst`
* [ ] Production applies a reviewed `bundle plan`; release tagged
* [ ] GitHub OIDC federation, no Databricks secrets in GitHub
* [ ] Actions pinned to commit SHAs; least-privilege `permissions:`; deploy concurrency groups

---

## 11. References

* [What are Declarative Automation Bundles?](https://docs.databricks.com/aws/en/dev-tools/bundles/)
* [Deployment modes](https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes/)
* [Migrate to the direct deployment engine](https://docs.databricks.com/aws/en/dev-tools/bundles/direct/)
* [Migrate existing resources to a bundle](https://docs.databricks.com/aws/en/dev-tools/bundles/migrate-resources/)
* [CI/CD workflows on Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/flows/)
* [Developer best practices on Databricks](https://docs.databricks.com/aws/en/developers/best-practices/)
* [Enable workload identity federation for GitHub Actions](https://docs.databricks.com/aws/en/dev-tools/auth/provider-github/)
* [Enable workload identity federation in CI/CD](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation-provider/)
