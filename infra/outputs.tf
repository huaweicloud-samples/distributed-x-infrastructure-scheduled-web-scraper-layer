output "bucket_name" {
  description = "Private bucket that keeps the snapshots"
  value       = huaweicloud_obs_bucket.results.bucket
}

output "function_name" {
  description = "Name of the scraper function"
  value       = huaweicloud_fgs_function.scraper.name
}

output "function_urn" {
  description = "URN of the scraper function"
  value       = huaweicloud_fgs_function.scraper.urn
}

output "timer_schedule" {
  description = "Cron expression of the scheduled trigger, empty when disabled"
  value       = var.enable_timer ? var.timer_schedule : "scheduled trigger is disabled (lightweight profile)"
}

output "timer_id" {
  description = "Trigger id, empty when the scheduled trigger is disabled"
  value       = try(one(huaweicloud_fgs_trigger.timer[*].id), "")
}

output "lts_group_id" {
  description = "Log group receiving structured function logs"
  value       = huaweicloud_lts_group.app.id
}

output "lts_stream_id" {
  description = "Log stream receiving structured function logs"
  value       = huaweicloud_lts_stream.app.id
}

output "invoke_command" {
  description = "Command used to invoke the function directly"
  value       = "hcloud fgs invoke --function-name ${huaweicloud_fgs_function.scraper.name} --body '{}'"
}
