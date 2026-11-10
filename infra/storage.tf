# Snapshots produced by each invocation are kept in a private bucket.
resource "huaweicloud_obs_bucket" "results" {
  bucket        = local.bucket_name
  acl           = "private"
  force_destroy = true
}
