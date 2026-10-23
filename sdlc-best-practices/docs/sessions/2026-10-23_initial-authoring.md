# 2026-10-23 -- Initial authoring of sdlc-best-practices

## Goal

Extend the workspace architecture and UC naming references with a deeper SDLC guide centered on Declarative Automation Bundles, show how much harder the same deployment is with the REST API or Terraform, and provide GitHub Actions CI/CD examples.

## Changes

* `docs/sdlc-best-practices-reference.md` -- principles, bundle deep dive, testing, promotion, rollback, checklist.
* `docs/deployment-complexity-comparison.md` -- measured comparison of bundle vs Terraform vs REST.
* `docs/github-actions-setup.md` -- service principals, environments, OIDC federation, branch protection.
* `examples/orders_bundle/` -- schema, volume, pipeline, job, `orders_lib` package, fixture generator, tests; targets dev, ci, tst, uat, prod.
* `examples/github-actions/.github/workflows/` -- `_deploy.yml`, `ci.yml`, `cd.yml`, `pr-cleanup.yml`.
* `examples/comparison/terraform/` and `examples/comparison/rest-api/`.

## Decisions

* **Five targets.** `ci` uses presets (`name_prefix: pr<N>_`) instead of development mode so each PR gets an isolated, CI-owned copy.
* **Deployer declared per shared target** with `service_principal_name: ${workspace.current_user.userName}` `CAN_MANAGE`. Satisfies `--strict` and blocks human deploys to shared targets.
* **Separate deploy and run-as identities.** `workload_principal` variable grants the run-as SP schema/volume privileges; it defaults to the deployer in dev and ci.
* **No `sync.exclude`.** Patterns matching nothing are warnings and break `--strict`; `.gitignore` already excludes build outputs.
* **Shared code as a wheel + editable install.** One `orders_lib` package used by pytest, the pipeline, and the job.
* **prod-plan environment** federated to the prod deploy SP so `bundle plan` can read real state before reviewers approve `prod`.
* **Actions pinned to commit SHAs** resolved with `git ls-remote` on the authoring date.

## Verification

* `pytest`: 13 passed. `ruff`: clean (EXE rules ignored; workspace filesystem marks files executable).
* `bundle validate`: all five targets pass. `--strict` passes for dev; shared targets pass when the deploying identity matches the declared deployer (verified by substituting a user principal in a scratch copy).
* `terraform validate` and `terraform fmt -check`: pass (Terraform 1.9.8, provider ~> 1.80).
* Workflows: YAML parses; reusable-workflow inputs cross-checked against every caller; all `uses:` pinned to 40-character SHAs. `actionlint` not run (binary download not available in this environment).

## Observations worth knowing

* `name_prefix: pr42_` yields schema `pr42orders` (trailing separator dropped) but job/pipeline `pr42_...`.
* `bundle validate -o json` leaves cross-resource `${resources.*}` references unresolved; resolved values are available on the referenced resource itself.

## Follow-ups

* Run the workflows end to end in a real repository and record the first-run results.
* Run `actionlint` in CI.
* Optionally render the reference as Databricks-branded HTML like the sibling documents.
