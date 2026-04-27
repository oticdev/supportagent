output "private_ip" {
  value       = google_sql_database_instance.postgres.private_ip_address
  description = "Private IP — used as host in DATABASE_URL"
}

output "connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "database_url" {
  # urlencode() percent-encodes special characters (e.g. # → %23) so they don't break URL parsing
  value     = "postgresql://${var.db_user}:${urlencode(var.db_password)}@${google_sql_database_instance.postgres.private_ip_address}/${var.db_name}"
  sensitive = true
}
