variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_vpc_connection_id" {
  type        = string
  description = "Ensures the private services access peering exists before the DB is created"
}

variable "db_name" {
  type    = string
  default = "relaypay"
}

variable "db_user" {
  type    = string
  default = "relay"
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "instance_tier" {
  type        = string
  description = "Cloud SQL machine type — e.g. db-f1-micro, db-g1-small, db-custom-2-4096"
  default     = "db-f1-micro"
}

variable "disk_size_gb" {
  type    = number
  default = 10
}

variable "high_availability" {
  type        = bool
  description = "Enable multi-zone HA (production only)"
  default     = false
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "backups_enabled" {
  type    = bool
  default = true
}
