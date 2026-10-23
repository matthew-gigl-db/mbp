# The orders_bundle deployment, rebuilt with the Databricks Terraform provider.
# ILLUSTRATIVE ONLY -- see ../../docs/deployment-complexity-comparison.md.
#
# Before the first `terraform init` you also need, per environment:
#   * an S3 bucket + DynamoDB table (or another backend) for remote state and locking,
#   * cloud credentials for the backend in the CI runner, separate from Databricks auth,
#   * a backend config file (envs/<env>.s3.tfbackend) and a tfvars file (envs/<env>.tfvars).

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.80"
    }
  }

  # Partial configuration: bucket/key/table come from envs/<env>.s3.tfbackend
  #   terraform init -backend-config=envs/prod.s3.tfbackend
  # Switching environments means re-initializing (or juggling workspaces) every time.
  backend "s3" {}
}

# Auth comes from DATABRICKS_HOST / DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET
# (or GitHub OIDC via DATABRICKS_AUTH_TYPE=github-oidc) in the environment.
provider "databricks" {
  host = var.workspace_host
}
