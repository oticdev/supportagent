# GCS static hosting + HTTPS Load Balancer + Managed SSL + CDN

# ── GCS bucket ────────────────────────────────────────────────────────────────
resource "google_storage_bucket" "site" {
  name                        = var.bucket_name
  location                    = "US"
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = !var.deletion_protection

  website {
    main_page_suffix = "index.html"
    not_found_page   = "index.html"   # SPA fallback
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type", "Cache-Control"]
    max_age_seconds = 3600
  }
}

resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.site.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# ── Backend bucket (enables CDN) ──────────────────────────────────────────────
resource "google_compute_backend_bucket" "site" {
  name        = "${var.prefix}-frontend-bb"
  bucket_name = google_storage_bucket.site.name
  project     = var.project_id
  enable_cdn  = true

  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 86400
    max_ttl           = 604800
    client_ttl        = 86400
    negative_caching  = true
    serve_while_stale = 86400
  }
}

# ── Reserved static IP — shared by HTTP and HTTPS forwarding rules ────────────
resource "google_compute_global_address" "lb_ip" {
  name    = "${var.prefix}-lb-ip"
  project = var.project_id
}

# ── HTTPS load balancer ───────────────────────────────────────────────────────
resource "google_compute_managed_ssl_certificate" "site" {
  name    = "${var.prefix}-ssl-cert"
  project = var.project_id

  managed {
    domains = [var.domain]
  }
}

resource "google_compute_url_map" "site" {
  name            = "${var.prefix}-frontend-urlmap"
  project         = var.project_id
  default_service = google_compute_backend_bucket.site.id
}

# HTTP → HTTPS redirect
resource "google_compute_url_map" "http_redirect" {
  name    = "${var.prefix}-http-redirect"
  project = var.project_id

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_https_proxy" "site" {
  name             = "${var.prefix}-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.site.id
  ssl_certificates = [google_compute_managed_ssl_certificate.site.id]
}

resource "google_compute_target_http_proxy" "redirect" {
  name    = "${var.prefix}-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "${var.prefix}-https-fwd"
  project               = var.project_id
  target                = google_compute_target_https_proxy.site.id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb_ip.address
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${var.prefix}-http-fwd"
  project               = var.project_id
  target                = google_compute_target_http_proxy.redirect.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb_ip.address
}

# ── GitHub Actions SA for frontend deploy ─────────────────────────────────────
resource "google_service_account" "github_deploy" {
  account_id   = "${var.prefix}-fe-deploy"
  display_name = "${var.prefix} Frontend Deploy SA"
  project      = var.project_id
}

resource "google_storage_bucket_iam_member" "github_deploy_storage" {
  bucket = google_storage_bucket.site.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.github_deploy.email}"
}

resource "google_project_iam_member" "github_deploy_cdn" {
  project = var.project_id
  role    = "roles/compute.networkAdmin"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "${var.prefix}-fe-gh-pool"
  project                   = var.project_id
  display_name              = "GH Actions FE ${var.prefix}"   # ≤32 chars
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "${var.prefix}-fe-gh-provider"
  project                            = var.project_id

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_wi" {
  service_account_id = google_service_account.github_deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}
