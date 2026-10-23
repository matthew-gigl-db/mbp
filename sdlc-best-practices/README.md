# SDLC Best Practices on Databricks

A deep dive into the software development lifecycle on Databricks with **Declarative Automation Bundles** (formerly Databricks Asset Bundles) and **GitHub Actions**, built on the environment model in [workspace-architecture](../workspace-architecture/docs/document.md) and the naming rules in [developer-user-isolation-in-uc](../developer-user-isolation-in-uc/docs/uc-naming-convention-reference.md).

## Documents

| Document | Read it for |
|---|---|
| [SDLC Best Practices Reference](docs/sdlc-best-practices-reference.md) | Principles, bundle deep dive (engine, targets, presets, variables, identity, data protection, plans), testing, promotion, rollback, checklist |
| [Deployment Complexity Comparison](docs/deployment-complexity-comparison.md) | The same deployment as a bundle, in Terraform, and on the raw REST API -- what each costs to own |
| [GitHub Actions Setup Guide](docs/github-actions-setup.md) | Service principals, GitHub environments, OIDC federation policies, branch protection, troubleshooting |
| [SDLC on Databricks presentation](docs/sdlc-best-practices-pitch.html) | Databricks-branded, single-file HTML deck for customer sessions: lifecycle, bundle deep dive, why bundles vs Terraform/REST, tagging for cost allocation, GitHub Actions, Genie Code in the bundle editor, adoption path. Open in a browser |

## Examples

| Path | What it is |
|---|---|
| [`examples/orders_bundle/`](examples/orders_bundle) | Complete bundle: UC schema + volume + grants, serverless Spark Declarative Pipeline (bronze/silver/gold), job with a wheel-based data quality gate, unit tests, five targets |
| [`examples/github-actions/.github/workflows/`](examples/github-actions/.github/workflows) | `ci.yml`, `cd.yml`, `pr-cleanup.yml`, and the reusable `_deploy.yml` |
| [`examples/comparison/terraform/`](examples/comparison/terraform) | The same deployment with the Databricks Terraform provider (illustrative) |
| [`examples/comparison/rest-api/`](examples/comparison/rest-api) | The same deployment on the REST API (illustrative, intentionally incomplete) |

## Quick start (dev target)

```bash
cd examples/orders_bundle
uv run --extra dev pytest -q             # unit tests, no workspace needed
databricks bundle validate --strict      # dev is the default target
databricks bundle deploy                 # personal copy: [dev <you>] ..., schema dev_<you>_orders
databricks bundle run orders_medallion --validate-only
```

The example uses catalogs `retail_dev`, `retail_tst`, `retail_uat`, and `retail`; change them in the `targets` block of `databricks.yml` to match your environment. Shared targets (`ci`, `tst`, `uat`, `prod`) are designed to be deployed only by CI/CD service principals.

## Validated with

Databricks CLI 1.22.1 (direct deployment engine), Terraform 1.9 with Databricks provider ~> 1.80, Python 3.10+, AWS, serverless compute.
