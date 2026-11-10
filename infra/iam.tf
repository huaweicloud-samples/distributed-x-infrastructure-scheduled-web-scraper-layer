# The function writes snapshot objects; no VPC attachment and no other data
# plane permission is required. Log delivery is configured on the function.
resource "huaweicloud_identity_agency" "functiongraph" {
  name                   = "${local.name_prefix}-fgs-agency"
  description            = "Agency for the scheduled scraper to write snapshot objects"
  delegated_service_name = "op_svc_cff"

  domain_roles = [
    "OBS OperateAccess",
  ]
}
