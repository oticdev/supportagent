variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "base_domain" {
  type        = string
  description = "e.g. relaypay.com"
}

variable "backend_github_repo" {
  type = string
}

variable "frontend_github_repo" {
  type = string
}

variable "support_email" {
  type    = string
  default = ""
}

# Sensitive — pass via TF_VAR_ env vars in CI, never commit to tfvars
variable "db_password" {
  type      = string
  sensitive = true
}

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
