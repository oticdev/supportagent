# Cloud SQL PostgreSQL 16 with pgvector — private IP only

resource "google_sql_database_instance" "postgres" {
  name             = "${var.prefix}-pg"
  database_version = "POSTGRES_16"
  region           = var.region
  project          = var.project_id

  deletion_protection = var.deletion_protection

  depends_on = [var.private_vpc_connection_id]

  settings {
    tier              = var.instance_tier
    edition           = "ENTERPRISE"
    availability_type = var.high_availability ? "REGIONAL" : "ZONAL"
    disk_autoresize   = true
    disk_size         = var.disk_size_gb

    ip_configuration {
      ipv4_enabled    = false          # No public IP
      private_network = var.vpc_id
    }

    backup_configuration {
      enabled    = var.backups_enabled
      start_time = "02:00"
      backup_retention_settings {
        retained_backups = 7
      }
    }

    insights_config {
      query_insights_enabled = true
    }
  }
}

resource "google_sql_database" "db" {
  name     = var.db_name
  instance = google_sql_database_instance.postgres.name
  project  = var.project_id
}

resource "google_sql_user" "app" {
  name     = var.db_user
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
  project  = var.project_id
}
