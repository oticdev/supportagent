variable "project_id" {
  type = string
}

variable "prefix" {
  type = string
}

variable "bucket_name" {
  type        = string
  description = "GCS bucket name — must be globally unique"
}

variable "domain" {
  type        = string
  description = "Custom domain, e.g. app.relaypay.com"
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "github_repo" {
  type        = string
  description = "org/repo — e.g. acme/supportagent-frontend"
}
