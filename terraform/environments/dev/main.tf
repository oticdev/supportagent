locals {
  env    = "dev"
  prefix = "relaypay-${local.env}"
}

module "networking" {
  source     = "../../modules/networking"
  project_id = var.project_id
  region     = var.region
  prefix     = local.prefix
}

module "database" {
  source     = "../../modules/cloudsql"
  project_id = var.project_id
  region     = var.region
  prefix     = local.prefix
  vpc_id     = module.networking.vpc_id

  private_vpc_connection_id = module.networking.private_vpc_connection

  db_name    = "relaypay"
  db_user    = "relay"
  db_password = var.db_password

  instance_tier       = "db-f1-micro"
  disk_size_gb        = 10
  high_availability   = false
  deletion_protection = false
  backups_enabled     = false
}

module "backend" {
  source           = "../../modules/backend"
  project_id       = var.project_id
  region           = var.region
  prefix           = local.prefix
  vpc_connector_id = module.networking.connector_id

  github_repo = var.backend_github_repo

  min_instances = 0
  max_instances = 3
  cpu           = "1"
  memory        = "512Mi"

  allowed_origins = "https://dev.${var.base_domain}"
  support_email   = var.support_email
  admin_username  = "admin"

  database_url         = module.database.database_url
  openai_api_key       = var.openai_api_key
  openrouter_api_key   = var.openrouter_api_key
  firecrawl_api_key    = var.firecrawl_api_key
  slack_webhook_url    = var.slack_webhook_url
  admin_password       = var.admin_password
  google_client_id     = var.google_client_id
  google_client_secret = var.google_client_secret
  google_refresh_token = var.google_refresh_token
}

module "frontend" {
  source      = "../../modules/frontend"
  project_id  = var.project_id
  prefix      = local.prefix
  bucket_name = "relaypay-dev-frontend"
  domain      = "dev.${var.base_domain}"
  github_repo = var.frontend_github_repo

  deletion_protection = false
}
