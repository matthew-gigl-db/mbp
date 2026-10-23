# GitHub Actions Setup Guide for Declarative Automation Bundles

**Author:** Matthew Giglia | Databricks Field Engineering  
**Version:** 1.0 | October 2026  
**Companion to:** [SDLC Best Practices Reference](sdlc-best-practices-reference.md)

---

## Overview

This guide wires the example workflows in [`examples/github-actions/.github/workflows`](../examples/github-actions/.github/workflows) to Databricks with **workload identity federation (GitHub OIDC)**. No Databricks secrets or tokens are stored in GitHub: each job requests a short-lived GitHub OIDC token, and the Databricks CLI exchanges it for a Databricks OAuth token for one specific service principal.

```
GitHub job (environment: prod) ── OIDC token: sub = repo:<org>/<repo>:environment:prod ──▶
Databricks account: federation policy on prod-deploy SP matches issuer + subject ──▶
short-lived Databricks token for prod-deploy SP ──▶ databricks bundle deploy -t prod
```

Binding each service principal to a **GitHub environment** (not a branch) means the protection rules on that environment -- required reviewers, allowed branches -- are what stand between a workflow and production credentials.

---

## 1. Copy the Files Into Your Repository

The workflows assume the bundle lives at `orders_bundle/` in the repository root:

```
<repo>/
├── .github/workflows/
│   ├── _deploy.yml      # reusable: validate / plan / deploy / destroy one target
│   ├── ci.yml           # pull requests
│   ├── cd.yml           # main -> tst -> uat -> prod
│   └── pr-cleanup.yml   # destroy the per-PR deployment
└── orders_bundle/       # copied from examples/orders_bundle
```

If your bundle lives elsewhere, change `BUNDLE_DIR` in `_deploy.yml`, the `working-directory` in `ci.yml` and `cd.yml`, and every `paths:` filter.

---

## 2. Platform Prerequisites (one time, platform team)

These sit outside the bundle and are typically managed with Terraform (see the [Enterprise Workspace Architecture](../../workspace-architecture/docs/document.md) reference).

| Item | dev workspace | tst | uat | prod |
|---|---|---|---|---|
| Catalog | `retail_dev` | `retail_tst` | `retail_uat` | `retail` |
| Deploy service principal | `orders-ci-deploy` | `orders-tst-deploy` | `orders-uat-deploy` | `orders-prod-deploy` |
| Run-as service principal | -- (ci runs as its deployer) | `orders-tst-run` | `orders-uat-run` | `orders-prod-run` |
| Groups | `data-engineers`, `data-consumers`, `platform-operators` (account level, assigned to each workspace) ||||

Grants and roles:

```sql
-- Repeat per environment with that environment's catalog and principals.
-- Service principals are referenced by application ID.
GRANT USE CATALOG, CREATE SCHEMA ON CATALOG retail_tst TO `<orders-tst-deploy-app-id>`;
GRANT USE CATALOG                ON CATALOG retail_tst TO `<orders-tst-run-app-id>`;
GRANT USE CATALOG                ON CATALOG retail_tst TO `data-engineers`;
```

* Add each deploy SP to its workspace with workspace access.
* Give each deploy SP the **Service principal: User** role on its run-as SP so it can set `run_as`.
* The deploy SP creates and owns the schema; the bundle grants the run-as SP only what the pipeline and job need (`workload_principal` in `databricks.yml`). Deploy SPs need no data access beyond schema ownership.

---

## 3. Create the GitHub Environments

In the repository: **Settings > Environments**.

| Environment | Protection rules | Environment variables |
|---|---|---|
| `ci` | none | `DATABRICKS_HOST` = dev workspace URL; `DATABRICKS_CLIENT_ID` = ci deploy SP app ID |
| `tst` | Deployment branches: `main` | `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID` (tst deploy SP), `RUN_AS_SERVICE_PRINCIPAL` (tst run-as SP) |
| `uat` | Deployment branches: `main`; reviewers optional | same three, uat values |
| `prod-plan` | Deployment branches: `main` | same three, **prod** values |
| `prod` | Deployment branches: `main`; **required reviewers**; optionally prevent self-review and add a wait timer | same three, prod values |

These are **variables**, not secrets. The application ID and host are not sensitive; access is controlled by the federation policy and environment rules.

`prod-plan` and `prod` both federate to the prod deploy SP because a plan must read that identity's deployment state. `prod-plan` only runs `bundle validate` and `bundle plan`; the reviewer gate sits on `prod`, after the plan is visible in the run summary.

---

## 4. Create One Federation Policy per Environment

As an account admin, create a **service principal federation policy** on each deploy SP. The easiest path is the account console: **User management > Service principals > (SP) > Credentials & secrets > Federation policies > Create policy**, choose **GitHub Actions**, and enter organization, repository, entity type **Environment**, and the environment name. The console fills in the issuer and audience.

The equivalent CLI call (run from a local terminal authenticated to the account, not the workspace web terminal):

```bash
# Numeric ID of the SP from its application ID
databricks account service-principals list --filter 'applicationId eq "<orders-prod-deploy-app-id>"'

databricks account service-principal-federation-policy create <numeric-sp-id> --json '{
  "oidc_policy": {
    "issuer": "https://token.actions.githubusercontent.com",
    "audiences": ["<audience>"],
    "subject": "repo:<org>/<repo>:environment:prod"
  }
}'
```

Replace each `<...>` placeholder, brackets included. For `<audience>`, use the value the GitHub Actions template in the account console shows (see [Configure a federation policy](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-federation-policy/)).

| Deploy SP | `subject` |
|---|---|
| ci | `repo:<org>/<repo>:environment:ci` |
| tst | `repo:<org>/<repo>:environment:tst` |
| uat | `repo:<org>/<repo>:environment:uat` |
| prod (two policies) | `repo:<org>/<repo>:environment:prod-plan` and `repo:<org>/<repo>:environment:prod` |

Note: for repositories created on or after July 15, 2026, GitHub includes numeric owner and repository IDs in the `sub` claim. Copy the exact `sub` format from the GitHub documentation for your repository, or from a decoded token, when the policy does not match.

---

## 5. How the Workflows Authenticate

`_deploy.yml` sets three environment variables; the CLI does the rest:

```yaml
jobs:
  bundle:
    environment: ${{ inputs.environment }}
    env:
      DATABRICKS_AUTH_TYPE: github-oidc
      DATABRICKS_HOST: ${{ vars.DATABRICKS_HOST }}
      DATABRICKS_CLIENT_ID: ${{ vars.DATABRICKS_CLIENT_ID }}
      BUNDLE_VAR_run_as_service_principal: ${{ vars.RUN_AS_SERVICE_PRINCIPAL }}
```

The **calling** job must grant `id-token: write` (GitHub only issues the token, and the `job_workflow_ref` claim, when the caller grants it):

```yaml
  prod:
    permissions:
      id-token: write
      contents: read
    uses: ./.github/workflows/_deploy.yml
```

The first step after installing the CLI is `databricks current-user me`, which proves federation works before anything is changed.

---

## 6. Branch Protection

On `main`:

* Require a pull request with at least one approval; dismiss stale approvals.
* Require status checks: **unit tests** and **deploy ci** from `ci.yml`.
* Require branches to be up to date before merging.
* Restrict who can push; disallow force pushes.
* Add `CODEOWNERS` for `.github/workflows/` and `orders_bundle/databricks.yml` -- changes to targets, permissions, and workflows deserve platform review.

---

## 7. What Each Workflow Does

### `ci.yml` -- every pull request

1. `unit` (no Databricks access): `ruff`, `pytest`, `uv build --wheel`.
2. `deploy-ci` (environment `ci`): `bundle validate --strict -t ci`, `bundle deploy -t ci` with `BUNDLE_VAR_pr_number`, then `bundle run orders_medallion --validate-only` to check the pipeline graph without processing data. Skipped for fork PRs, which cannot obtain OIDC tokens.

Resources are named `pr<N>_orders_medallion`, `pr<N>_orders_refresh`, and schema `pr<N>orders` in `retail_dev`, so concurrent PRs never collide.

### `pr-cleanup.yml` -- pull request closed

Runs `bundle destroy -t ci --auto-approve` for that PR number. The reusable workflow refuses to destroy any other target.

### `cd.yml` -- push to `main` or manual dispatch

| Job | Environment | Action |
|---|---|---|
| `unit` | -- | lint and tests on the exact commit |
| `tst` | `tst` | validate, deploy, seed fixture orders into the landing volume, run `orders_refresh` (pipeline + quality gate) |
| `uat` | `uat` | validate, deploy |
| `plan-prod` | `prod-plan` | validate, `bundle plan` to the run summary, upload `plan.json` |
| `prod` | `prod` (reviewers) | download `plan.json`, `bundle deploy --plan plan.json --fail-on-active-runs` |
| `release-tag` | -- | tag the deployed commit `orders-prod-<date>-<run>` |

The workflow-level `concurrency: cd-orders` with `cancel-in-progress: false` queues releases instead of cancelling one mid-deploy; the per-target concurrency group in `_deploy.yml` also protects against a manual run colliding with an automatic one.

### Rollback

**Actions > cd > Run workflow**, set `ref` to the last good `orders-prod-*` tag. The same tests, plan, and approval apply.

---

## 8. Supply-Chain Hardening

* Third-party actions are pinned to **full commit SHAs** with the tag in a comment (`actions/checkout@<sha> # v7.0.1`). Let Dependabot or Renovate propose SHA bumps.
* The CLI version is pinned in `_deploy.yml` (`DATABRICKS_CLI_VERSION`) and constrained in `databricks.yml` (`databricks_cli_version`).
* Workflow-level `permissions: contents: read`; `id-token: write` only on jobs that deploy; `contents: write` only on `release-tag`.
* No `pull_request_target`: untrusted fork code never runs with credentials.
* Plans are uploaded as short-lived artifacts (7 days) and applied only by the approved job.

---

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `databricks current-user me` fails with a token exchange error | Federation policy `subject` does not match the token's `sub` (environment name, org/repo, or numeric-ID format), or wrong `audiences` |
| `Unable to get ACTIONS_ID_TOKEN_REQUEST_URL` | Calling job lacks `permissions: id-token: write`, or the run comes from a fork |
| `--strict`: workspace folder has permissions not configured in bundle | Deploying identity is not the SP declared with `CAN_MANAGE` for that target -- usually a human deploying a shared target |
| `run_as` permission error | Deploy SP lacks the Service principal: User role on the run-as SP |
| `PERMISSION_DENIED` creating the schema | Deploy SP lacks `USE CATALOG` / `CREATE SCHEMA` on the catalog |
| Pipeline fails reading the landing volume | Run-as SP lacks `USE CATALOG`, or the volume grant (`READ_VOLUME`) was removed |
| Quality gate fails in `tst` with `gold_rows=0` | Fixture upload step skipped or landing path changed |
| `deploy --plan` rejects the plan | The target changed between plan and apply; re-run from `plan-prod` |
