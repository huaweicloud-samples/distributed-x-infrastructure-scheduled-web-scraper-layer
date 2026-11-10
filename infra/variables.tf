variable "region" {
  description = "Region where the function, bucket and log resources are created"
  type        = string
  default     = "cn-north-4"
}

variable "app_name" {
  description = "Prefix used for every resource name"
  type        = string
  default     = "scheduled-web-scraper"
}

variable "obs_bucket_name" {
  description = "Globally unique bucket name; leave empty to derive one from app_name and region"
  type        = string
  default     = ""
}

variable "function_runtime" {
  description = "FunctionGraph Python runtime"
  type        = string
  default     = "Python3.9"
}

variable "function_memory_size" {
  description = "Function memory in MB"
  type        = number
  default     = 512
}

variable "function_timeout" {
  description = "Function timeout in seconds"
  type        = number
  default     = 600
}

variable "enable_timer" {
  description = "Create the scheduled trigger; set false to invoke the function manually for a lightweight check"
  type        = bool
  default     = true
}

variable "timer_schedule" {
  description = "Quartz-style cron expression for the scheduled trigger (second minute hour day month weekday)"
  type        = string
  default     = "0 59 6,10,14,18 * * ?"
}

variable "timer_schedule_type" {
  description = "Schedule type of the trigger"
  type        = string
  default     = "Cron"
}

variable "target_url" {
  description = "Page address fetched by each invocation"
  type        = string
  default     = "https://www.example.com"
}

variable "result_prefix" {
  description = "Key prefix for the snapshot objects"
  type        = string
  default     = "snapshots"
}

variable "lts_ttl_in_days" {
  description = "Log retention in days"
  type        = number
  default     = 7
}

variable "service_name" {
  description = "Service name written into structured log lines"
  type        = string
  default     = "scheduled-web-scraper"
}

variable "log_level" {
  description = "Minimum level emitted by the function logger"
  type        = string
  default     = "INFO"
}
