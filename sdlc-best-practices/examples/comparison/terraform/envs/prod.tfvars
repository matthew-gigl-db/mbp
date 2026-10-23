# One of these per environment (dev.tfvars, tst.tfvars, uat.tfvars, prod.tfvars).
workspace_host           = "https://<prod-workspace-host>"
env                      = "prod"
catalog                  = "retail"
run_as_service_principal = "<prod-run-as-sp-application-id>"
wheel_path               = "../../orders_bundle/dist/orders_lib-0.1.0-py3-none-any.whl"
