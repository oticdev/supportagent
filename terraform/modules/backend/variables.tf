variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "prefix" {
  type = string
}

variable "vpc_connector_id" {
  type = string
}

variable "github_repo" {
  type        = string
  description = "org/repo — e.g. acme/supportagent-backend"
}

variable "image_tag" {
  type        = string
  description = "Docker image tag to deploy"
  default     = "latest"
}

variable "deletion_protection" {
  type    = bool
  default = false
}

# ── Scaling / resources ───────────────────────────────────────────────────────
variable "min_instances" {
  type    = number
  default = 0
}

variable "max_instances" {
  type    = number
  default = 10
}

variable "cpu" {
  type    = string
  default = "1"
}

variable "memory" {
  type    = string
  default = "512Mi"
}

# ── Non-sensitive env vars ────────────────────────────────────────────────────
variable "llm_model" {
  type    = string
  default = "openai/gpt-4o-mini"
}

variable "embed_model" {
  type    = string
  default = "text-embedding-3-small"
}

variable "tts_voice" {
  type    = string
  default = "alloy"
}

variable "support_email" {
  type    = string
  default = ""
}

variable "allowed_origins" {
  type = string
}

variable "admin_username" {
  type    = string
  default = "admin"
}

# ── Sensitive values (stored in Secret Manager) ───────────────────────────────
variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "openrouter_api_key" {
  type      = string
  sensitive = true
}

variable "firecrawl_api_key" {
  type      = string
  sensitive = true
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "slack_webhook_url" {
  type      = string
  sensitive = true
  default   = ""
}

variable "admin_password" {
  type      = string
  sensitive = true
}

variable "google_client_id" {
  type      = string
  sensitive = true
  default   = ""
}

variable "google_client_secret" {
  type      = string
  sensitive = true
  default   = ""
}

variable "google_refresh_token" {
  type      = string
  sensitive = true
  default   = ""
}
