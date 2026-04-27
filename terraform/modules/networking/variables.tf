variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region (e.g. us-central1)"
}

variable "prefix" {
  type        = string
  description = "Resource name prefix — typically 'appname-environment'"
}
