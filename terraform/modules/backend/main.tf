# Cloud Run service + Artifact Registry + Secret Manager + Workload Identity

# ── Artifact Registry ─────────────────────────────────────────────────────────
resource "google_artifact_registry_repository" "images" {
  repository_id = "${var.prefix}-images"
  format        = "DOCKER"
  location      = var.region
  project       = var.project_id
  description   = "Docker images for ${var.prefix} backend"
}

# ── Service account Cloud Run runs as ─────────────────────────────────────────
resource "google_service_account" "cloudrun" {
  account_id   = "${var.prefix}-cr-sa"
  display_name = "${var.prefix} Cloud Run SA"
  project      = var.project_id
}

# Allow Cloud Run SA to read secrets
resource "google_project_iam_member" "cloudrun_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

# Allow Cloud Run SA to pull images from Artifact Registry
resource "google_project_iam_member" "cloudrun_ar_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.cloudrun.email}"
}

# ── Secrets (values populated manually or via CI after first apply) ───────────
locals {
  secrets = {
    openai-api-key       = var.openai_api_key
    openrouter-api-key   = var.openrouter_api_key
    firecrawl-api-key    = var.firecrawl_api_key
    database-url         = var.database_url
    slack-webhook-url    = var.slack_webhook_url
    admin-password       = var.admin_password
    google-client-id     = var.google_client_id
    google-client-secret = var.google_client_secret
    google-refresh-token = var.google_refresh_token
  }
}

resource "google_secret_manager_secret" "app" {
  for_each  = local.secrets
  secret_id = "${var.prefix}-${each.key}"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "app" {
  for_each    = local.secrets
  secret      = google_secret_manager_secret.app[each.key].id
  secret_data = each.value
}

# ── Cloud Run service ─────────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "backend" {
  name     = "${var.prefix}-api"
  location = var.region
  project  = var.project_id

  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.deletion_protection

  template {
    service_account = google_service_account.cloudrun.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/backend:${var.image_tag}"

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle = true   # Scale to zero when idle
      }

      # Non-sensitive env vars
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
      env {
        name  = "EMBED_MODEL"
        value = var.embed_model
      }
      env {
        name  = "TTS_VOICE"
        value = var.tts_voice
      }
      env {
        name  = "SUPPORT_EMAIL"
        value = var.support_email
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
      env {
        name  = "ADMIN_USERNAME"
        value = var.admin_username
      }

      # Sensitive env vars from Secret Manager
      dynamic "env" {
        for_each = {
          OPENAI_API_KEY          = "openai-api-key"
          OPENROUTER_API_KEY      = "openrouter-api-key"
          FIRECRAWL_API_KEY       = "firecrawl-api-key"
          DATABASE_URL            = "database-url"
          SLACK_WEBHOOK_URL       = "slack-webhook-url"
          ADMIN_PASSWORD          = "admin-password"
          GOOGLE_CLIENT_ID        = "google-client-id"
          GOOGLE_CLIENT_SECRET    = "google-client-secret"
          GOOGLE_OAUTH_REFRESH_TOKEN = "google-refresh-token"
        }
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_version.app]
}

# Allow unauthenticated public traffic
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Workload Identity Federation for GitHub Actions ───────────────────────────
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "${var.prefix}-gh-pool"
  project                   = var.project_id
  display_name              = "GH Actions ${var.prefix}"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "${var.prefix}-gh-provider"
  project                            = var.project_id

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Service account GitHub Actions uses to push images and deploy
resource "google_service_account" "github_deploy" {
  account_id   = "${var.prefix}-gh-deploy"
  display_name = "${var.prefix} GitHub Deploy SA"
  project      = var.project_id
}

resource "google_service_account_iam_member" "github_wi" {
  service_account_id = google_service_account.github_deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

resource "google_project_iam_member" "github_deploy_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

resource "google_project_iam_member" "github_deploy_ar" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

resource "google_project_iam_member" "github_deploy_sa_act_as" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}
