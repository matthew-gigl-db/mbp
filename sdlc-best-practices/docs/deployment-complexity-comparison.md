# Deployment Complexity: Bundles vs. Terraform vs. the REST API

**Author:** Matthew Giglia | Databricks Field Engineering  
**Version:** 1.0 | October 2026  
**Companion to:** [SDLC Best Practices Reference](sdlc-best-practices-reference.md)

---

## Overview

The same data product -- one UC schema, one volume, grants, a serverless Lakeflow Spark Declarative Pipeline, and a scheduled job with a wheel-based quality gate -- was implemented three ways:

| Implementation | Location | Status |
|---|---|---|
| Declarative Automation Bundle | [`examples/orders_bundle/`](../examples/orders_bundle) | `bundle validate` passes for all five targets (CLI 1.22.1); `--strict` passes for `dev`, and for shared targets when run as their deploy identity |
| Terraform (Databricks provider ~> 1.80) | [`examples/comparison/terraform/`](../examples/comparison/terraform) | `terraform validate` and `terraform fmt -check` pass |
| REST API (Python + `requests`) | [`examples/comparison/rest-api/deploy_orders_rest.py`](../examples/comparison/rest-api/deploy_orders_rest.py) | Syntax- and lint-clean; **illustrative, intentionally incomplete** |

The headline is not line count. The three are roughly the same size. The difference is **what each one covers** and **what you own** once it exists.

---

## 1. Size and Coverage

Non-blank, non-comment lines of deployment definition (application code under `src/` is identical and excluded):

| | Bundle | Terraform | REST API |
|---|---|---|---|
| Deployment definition | **260** (`databricks.yml` 167 + `resources/` 93) | **251** `.tf` + **10 per environment** (tfvars + backend) | **259** |
| Environments covered | 5: `dev`, `ci`, `tst`, `uat`, `prod` | 4 (`ci` per-PR not implemented) | 4 (`ci` per-PR not implemented) |
| Per-developer isolation | automatic (`mode: development`) | manual: prefix variable **and** a separate state key per developer | manual naming function |
| Per-PR environments | yes (`name_prefix` + `pr_number`) | needs dynamic backend keys and cleanup | not implemented |
| Plan before apply | `bundle plan`, replayable `--plan plan.json` | `terraform plan -out` | not implemented |
| State and locking | managed in the workspace | external backend (S3 bucket + DynamoDB table) you provision | hand-rolled file lock with a race window |
| Code sync incl. deletions | built in, honors `.gitignore` | one `databricks_workspace_file` per file via `fileset()`; no `.gitignore` | hand-written upload + stale-file deletion |
| Artifact build | `artifacts:` block, built on deploy | must be built **before** `terraform plan` | subprocess + upload + versioned path |
| Protect prod data | `lifecycle.prevent_destroy` **per target** | `prevent_destroy` cannot be a variable; duplicate blocks or accept risk | hard-coded env list |
| Credentials | GitHub OIDC built in | GitHub OIDC (provider) + separate cloud creds for the backend | OAuth M2M with a client secret; token refresh not handled |
| Approx. API surface you code against | 0 | 12 resource types | 15 endpoints, 29 call sites |

The `targets` block accounts for 118 of the bundle's 260 lines, and much of that is the five-line `tags` preset repeated per target. Adding a sixth environment costs about 20 lines and no new logic. Adding a sixth environment to the REST script means another entry in `ENVIRONMENTS` plus whatever edge cases it exposes; in Terraform it means another backend, tfvars file, and state to operate.

---

## 2. What You Own After Day One

### REST API

The script in `comparison/rest-api/` is the clearest illustration of what a bundle hides. To deploy five objects it must:

1. Exchange client credentials for an OAuth token (and eventually refresh it).
2. Resolve the current identity to derive paths and dev prefixes.
3. Implement retries for 429 and 5xx responses.
4. Upload every source file, create every directory, and delete files that no longer exist.
5. Build a wheel and upload it to a unique, versioned path so serverless does not cache stale code.
6. Create-or-update each UC object, in dependency order, by hand.
7. **Reconcile** grants: compute adds and removes against current state without revoking privileges it never granted.
8. Store resource IDs in a state file (names are not unique keys), and read them back next time.
9. Implement a deployment lock -- and accept the race window the simple version has.
10. Translate permission vocabularies per object type (`CAN_MANAGE_RUN` on jobs is `CAN_RUN` on pipelines).
11. Thread the pipeline ID into the job and the wheel path into the environment spec.
12. Decide when a missing resource means "delete" and when it means "never touch".

Its `KNOWN GAPS` footer lists what is still missing: plan/diff, schema validation, drift detection, OIDC, pagination, stale-lock recovery, destroy, selective deploy, variables and lookups, and a create/update/delete path for every additional resource type (dashboards, apps, serving endpoints, Lakebase, Genie spaces). Each gap is a feature the CLI team already maintains.

**Use the REST API (or SDK) for** operational automation and custom tooling -- triggering runs, querying state, one-off admin tasks -- not as a deployment system.

### Terraform

Terraform is a sound choice for **platform** resources and remains the right tool for accounts, workspaces, networking, metastores, storage credentials, and identity. For **workload** deployment, the example shows where it adds weight:

* **Bootstrap infrastructure.** Remote state needs a bucket and lock table per organization, IAM to reach them, and a backend config per environment -- before the first `init`.
* **Environment switching.** Each environment is a separate state. Developers need their own state keys to avoid overwriting each other; per-PR environments need dynamic keys plus cleanup of orphaned state.
* **Files are resources.** Every source file is a `databricks_workspace_file`. New files need `fileset()` patterns; nothing honors `.gitignore`.
* **Build ordering.** `filemd5()` on the wheel is evaluated at plan time, so the wheel must exist before `terraform plan` -- an extra CI step outside Terraform.
* **Authoritative resources.** `databricks_grants` and `databricks_permissions` replace the full set for their object. Grants added by an admin outside Terraform are revoked on the next apply. Sometimes desired, often surprising.
* **Static lifecycle.** `prevent_destroy` cannot be driven by a variable. Protecting only prod requires duplicated resource blocks or modules per environment.
* **No development mode.** Prefixing, pausing schedules, development pipelines, and tagging are all `locals` and conditionals you write and test (see `main.tf`).

### Bundles

You own the YAML and the `targets` block. The CLI owns authentication (including GitHub OIDC), sync, artifacts, ordering, state, locking, planning, mode behaviors, validation, and every resource type's API -- and it is upgraded by changing one pinned version.

---

## 3. Side by Side: One Concern, Three Ways

### Pause schedules everywhere except prod

| Bundle | Terraform | REST API |
|---|---|---|
| `presets: { trigger_pause_status: PAUSED }` on non-prod targets (and automatic in `mode: development`) | `pause_status = local.is_prod ? "UNPAUSED" : "PAUSED"` on every scheduled resource | `"pause_status": "PAUSED" if env["paused"] else "UNPAUSED"` in every payload |

### Give the job the pipeline's ID

| Bundle | Terraform | REST API |
|---|---|---|
| `pipeline_id: ${resources.pipelines.orders_medallion.id}` | `pipeline_id = databricks_pipeline.orders_medallion.id` | capture the create response, persist it in state, read it back on the next run, pass it into the job payload |

### Personal dev copy for each engineer

| Bundle | Terraform | REST API |
|---|---|---|
| `databricks bundle deploy` (dev is the default target) | set `developer_short_name`, choose a unique state key, `init -reconfigure`, apply | pass `--env dev`; naming function derives prefixes; state file lives under the user's home |

### Ship to prod exactly what was reviewed

| Bundle | Terraform | REST API |
|---|---|---|
| `bundle plan -o json > plan.json`, approve, `bundle deploy --plan plan.json` | `terraform plan -out=tfplan`, approve, `terraform apply tfplan` (plan file contains sensitive values; protect the artifact) | not available |

---

## 4. Recommendation

| Layer | Tool | Owner |
|---|---|---|
| Account, workspaces, networking, metastore, storage credentials, external locations | Terraform | Platform team |
| Catalogs per environment, catalog-level grants, service principals, federation policies, cluster policies | Terraform (or bundles for catalogs, where the platform team prefers one tool) | Platform team |
| Schemas, volumes, schema/volume grants, jobs, pipelines, apps, dashboards, serving endpoints, Genie spaces | **Declarative Automation Bundles** | Data product teams |
| Runs, backfills, operational scripts, custom tooling | CLI / SDK / REST API | Anyone, from CI or notebooks |

The contract between the platform and workload layers is small and explicit: **a catalog per environment, a deploy service principal and a run-as service principal per shared environment, and the grants between them.** Everything inside that boundary belongs in a bundle.

---

## 5. Reproducing the Measurements

```bash
cd sdlc-best-practices/examples

# Bundle: validate every target (shared targets pass --strict when run as their deploy SP)
for t in dev ci tst uat prod; do
  (cd orders_bundle && databricks bundle validate -t $t --var pr_number=42 \
     --var run_as_service_principal=<sp-application-id>)
done

# Terraform: offline validation
(cd comparison/terraform && terraform init -backend=false && terraform validate && terraform fmt -check)

# Line counts (non-blank, non-comment)
grep -vhE '^\s*(#|$)' orders_bundle/databricks.yml orders_bundle/resources/*/*.yml | wc -l
grep -vhE '^\s*(#|$)' comparison/terraform/*.tf | wc -l
grep -vhE '^\s*(#|$)' comparison/rest-api/deploy_orders_rest.py | wc -l
```
