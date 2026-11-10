# Structured JSON log lines go to Log Tank Service through the service-managed
# log configuration on the function; the function itself holds no log credential.
resource "huaweicloud_lts_group" "app" {
  group_name  = "${local.name_prefix}-lts"
  ttl_in_days = var.lts_ttl_in_days
}

resource "huaweicloud_lts_stream" "app" {
  group_id    = huaweicloud_lts_group.app.id
  stream_name = "${local.name_prefix}-app"
  ttl_in_days = var.lts_ttl_in_days
}
