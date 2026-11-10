terraform {
  required_version = ">= 1.5.0"

  required_providers {
    huaweicloud = {
      source  = "huaweicloud/huaweicloud"
      version = ">= 1.97.0"
    }
  }
}

provider "huaweicloud" {
  region = var.region
}

locals {
  name_prefix = var.app_name
  bucket_name = (
    var.obs_bucket_name != ""
    ? var.obs_bucket_name
    : "${var.app_name}-${var.region}-results"
  )
}
