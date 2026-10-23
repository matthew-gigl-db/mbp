variable "workspace_host" {
  type        = string
  description = "Workspace URL for this environment."
}

variable "env" {
  type        = string
  description = "Environment name: dev, tst, uat, or prod."
  validation {
    condition     = contains(["dev", "tst", "uat", "prod"], var.env)
    error_message = "env must be dev, tst, uat, or prod."
  }
}

variable "catalog" {
  type        = string
  description = "Unity Catalog catalog for this environment."
}

variable "developer_short_name" {
  type        = string
  default     = ""
  description = "dev only: personal prefix. Each developer ALSO needs their own state key."
}

variable "run_as_service_principal" {
  type        = string
  default     = ""
  description = "Application ID of the service principal that runs shared-environment workloads."
}

variable "bundle_source_dir" {
  type        = string
  default     = "../../orders_bundle"
  description = "Local path of the project source to upload."
}

variable "wheel_path" {
  type        = string
  description = "Local path of the wheel. Must be built BEFORE terraform plan (uv build --wheel)."
}

variable "groups" {
  type = object({
    engineers = string
    consumers = string
    operators = string
  })
  default = {
    engineers = "data-engineers"
    consumers = "data-consumers"
    operators = "platform-operators"
  }
}

variable "tags" {
  type = map(string)
  default = {
    project      = "orders-medallion"
    businessUnit = "Retail Analytics"
    costCenter   = "CC-0000"
    owner        = "data-engineering"
  }
}
