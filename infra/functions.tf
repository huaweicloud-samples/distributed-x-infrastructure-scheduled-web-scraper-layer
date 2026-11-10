locals {
  function_zip = "${path.module}/../build/function.zip"

  # A missing package produces a clear runtime error instead of an opaque
  # "Invalid function argument" from filebase64 during plan.
  function_code = (
    fileexists(local.function_zip)
    ? filebase64(local.function_zip)
    : base64encode("raise RuntimeError('Missing deployment package: build/function.zip. Run scripts/package-function.sh first.')")
  )

  # FunctionGraph rejects environment variables whose value is an empty string
  # (FSS.1009 Invalid function UserData), so filter them out before encoding.
  env_without_empty = {
    for k, v in {
      REGION         = var.region
      OBS_BUCKET     = huaweicloud_obs_bucket.results.bucket
      OBS_ENDPOINT   = "https://obs.${var.region}.myhuaweicloud.com"
      TARGET_URL     = var.target_url
      RESULT_PREFIX  = var.result_prefix
      SERVICE_NAME   = var.service_name
      LOG_LEVEL      = var.log_level
      LTS_GROUP_ID   = huaweicloud_lts_group.app.id
      LTS_STREAM_ID  = huaweicloud_lts_stream.app.id
      TIMER_SCHEDULE = var.timer_schedule
    } : k => v if v != null && v != ""
  }
}

resource "huaweicloud_fgs_function" "scraper" {
  name        = "${local.name_prefix}-scraper"
  app         = "default"
  agency      = huaweicloud_identity_agency.functiongraph.name
  handler     = "index.handler"
  runtime     = var.function_runtime
  memory_size = var.function_memory_size
  timeout     = var.function_timeout

  # The function code and its third-party libraries travel in one archive.
  code_type     = "zip"
  code_filename = "function.zip"
  func_code     = local.function_code

  enable_lts_log = true
  log_group_id   = huaweicloud_lts_group.app.id
  log_stream_id  = huaweicloud_lts_stream.app.id

  user_data = jsonencode(local.env_without_empty)

  # IAM agency propagation is asynchronous; creating the function too early
  # fails with FSS.1501 The delegate not exist.
  depends_on = [huaweicloud_identity_agency.functiongraph]
}

# A scheduled trigger invokes the function on the configured cron expression.
# The lightweight profile disables it so the function can be invoked directly.
resource "huaweicloud_fgs_trigger" "timer" {
  count = var.enable_timer ? 1 : 0

  function_urn = trimsuffix(huaweicloud_fgs_function.scraper.urn, ":latest")
  type         = "TIMER"

  timer {
    name          = "${local.name_prefix}-cron"
    schedule      = var.timer_schedule
    schedule_type = var.timer_schedule_type
  }

  depends_on = [huaweicloud_fgs_function.scraper]
}
