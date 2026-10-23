# ---------------------------------------------------------------------------
# Naming and environment logic. In a bundle: `mode: development` + presets.
# ---------------------------------------------------------------------------
data "databricks_current_user" "me" {}

locals {
  is_dev   = var.env == "dev"
  is_prod  = var.env == "prod"
  shared   = !local.is_dev
  dev_tag  = local.is_dev ? { dev = var.developer_short_name } : {}
  tags     = merge(var.tags, { env = var.env }, local.dev_tag)
  prefix   = local.is_dev ? "[dev ${var.developer_short_name}] " : ""
  schema   = local.is_dev ? "dev_${var.developer_short_name}_orders" : "orders"
  root     = "${data.databricks_current_user.me.home}/.bundle/orders_tf/${var.env}"
  src_root = "${var.bundle_source_dir}/src"

  # Every file has to be enumerated and uploaded explicitly.
  pipeline_files = fileset("${local.src_root}/pipelines/orders_medallion", "**/*.py")
  library_files  = fileset("${local.src_root}/orders_lib", "**/*.py")
}

# ---------------------------------------------------------------------------
# Unity Catalog. NOTE: Terraform's prevent_destroy cannot be set from a variable,
# so protecting prod data means either duplicating these blocks per environment
# or accepting that `terraform destroy` on prod drops the schema and volume.
# ---------------------------------------------------------------------------
resource "databricks_schema" "orders" {
  catalog_name = var.catalog
  name         = local.schema
  comment      = "Orders medallion data product (bronze, silver, gold). Managed by Terraform."
  properties   = local.tags
  # force_destroy deletes all tables inside on destroy -- dangerous outside dev.
  force_destroy = local.is_dev
}

resource "databricks_grants" "orders_schema" {
  schema = databricks_schema.orders.id
  # databricks_grants is AUTHORITATIVE: any grant not listed here (for example one an
  # admin added by hand) is revoked on the next apply.
  grant {
    principal  = var.groups.engineers
    privileges = ["USE_SCHEMA", "SELECT"]
  }
  grant {
    principal  = var.groups.consumers
    privileges = ["USE_SCHEMA", "SELECT"]
  }
}

resource "databricks_volume" "landing" {
  catalog_name = var.catalog
  schema_name  = databricks_schema.orders.name
  name         = "landing"
  volume_type  = "MANAGED"
  comment      = "Raw order files (JSON)."
}

resource "databricks_grants" "landing_volume" {
  volume = databricks_volume.landing.id
  grant {
    principal  = var.groups.engineers
    privileges = ["READ_VOLUME", "WRITE_VOLUME"]
  }
}

# ---------------------------------------------------------------------------
# Source code + artifacts. Bundles sync these automatically, honoring .gitignore.
# ---------------------------------------------------------------------------
resource "databricks_workspace_file" "pipeline_src" {
  for_each = local.pipeline_files
  source   = "${local.src_root}/pipelines/orders_medallion/${each.value}"
  path     = "${local.root}/files/src/pipelines/orders_medallion/${each.value}"
}

resource "databricks_workspace_file" "library_src" {
  for_each = local.library_files
  source   = "${local.src_root}/orders_lib/${each.value}"
  path     = "${local.root}/files/src/orders_lib/${each.value}"
}

resource "databricks_workspace_file" "pyproject" {
  source = "${var.bundle_source_dir}/pyproject.toml"
  path   = "${local.root}/files/pyproject.toml"
}

# The wheel must be built outside Terraform first. Content hash in the path forces
# serverless to pick up new code (bundles: artifacts_dynamic_version).
resource "databricks_workspace_file" "wheel" {
  source = var.wheel_path
  path   = "${local.root}/artifacts/${filemd5(var.wheel_path)}/${basename(var.wheel_path)}"
}

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
resource "databricks_pipeline" "orders_medallion" {
  name        = "${local.prefix}orders_medallion"
  catalog     = var.catalog
  schema      = databricks_schema.orders.name
  serverless  = true
  continuous  = false
  photon      = true
  development = local.is_dev
  root_path   = "${local.root}/files/src/pipelines/orders_medallion"
  tags        = local.tags

  library {
    glob {
      include = "${local.root}/files/src/pipelines/orders_medallion/transformations/**"
    }
  }

  environment {
    dependencies = ["--editable ${local.root}/files"]
  }

  configuration = {
    "orders.landing_path" = "/Volumes/${var.catalog}/${databricks_schema.orders.name}/${databricks_volume.landing.name}/orders"
  }

  dynamic "run_as" {
    for_each = local.shared ? [1] : []
    content {
      service_principal_name = var.run_as_service_principal
    }
  }

  # Source files are referenced by path, not by resource, so ordering must be forced.
  depends_on = [
    databricks_workspace_file.pipeline_src,
    databricks_workspace_file.library_src,
    databricks_workspace_file.pyproject,
  ]
}

# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------
resource "databricks_job" "orders_refresh" {
  name                = "${local.prefix}orders_refresh"
  description         = "Refreshes the orders medallion pipeline and fails if gold data breaks quality rules."
  max_concurrent_runs = local.is_dev ? 4 : 1
  tags                = local.tags

  schedule {
    quartz_cron_expression = "0 0 6 * * ?"
    timezone_id            = "UTC"
    pause_status           = local.is_prod ? "UNPAUSED" : "PAUSED"
  }

  parameter {
    name    = "catalog"
    default = var.catalog
  }
  parameter {
    name    = "schema"
    default = databricks_schema.orders.name
  }

  task {
    task_key = "refresh_pipeline"
    pipeline_task {
      pipeline_id  = databricks_pipeline.orders_medallion.id
      full_refresh = false
    }
  }

  task {
    task_key        = "quality_gate"
    environment_key = "default"
    depends_on {
      task_key = "refresh_pipeline"
    }
    python_wheel_task {
      package_name = "orders_lib"
      entry_point  = "quality_gate"
      parameters   = ["--catalog", "{{job.parameters.catalog}}", "--schema", "{{job.parameters.schema}}"]
    }
  }

  environment {
    environment_key = "default"
    spec {
      environment_version = "4"
      dependencies        = [databricks_workspace_file.wheel.workspace_path]
    }
  }

  dynamic "run_as" {
    for_each = local.shared ? [1] : []
    content {
      service_principal_name = var.run_as_service_principal
    }
  }
}

# ---------------------------------------------------------------------------
# Object permissions. Note the per-type vocabulary (CAN_MANAGE_RUN vs CAN_RUN).
# databricks_permissions is also authoritative for the object it manages.
# ---------------------------------------------------------------------------
resource "databricks_permissions" "job" {
  job_id = databricks_job.orders_refresh.id

  access_control {
    group_name       = var.groups.engineers
    permission_level = local.is_dev ? "CAN_MANAGE" : "CAN_VIEW"
  }
  dynamic "access_control" {
    for_each = local.shared ? [1] : []
    content {
      group_name       = var.groups.operators
      permission_level = "CAN_MANAGE_RUN"
    }
  }
}

resource "databricks_permissions" "pipeline" {
  pipeline_id = databricks_pipeline.orders_medallion.id

  access_control {
    group_name       = var.groups.engineers
    permission_level = local.is_dev ? "CAN_MANAGE" : "CAN_VIEW"
  }
  dynamic "access_control" {
    for_each = local.shared ? [1] : []
    content {
      group_name       = var.groups.operators
      permission_level = "CAN_RUN"
    }
  }
}

output "job_id" {
  value = databricks_job.orders_refresh.id
}

output "pipeline_id" {
  value = databricks_pipeline.orders_medallion.id
}
