# VPC network, private services access (Cloud SQL), and VPC connector (Cloud Run)

resource "google_compute_network" "vpc" {
  name                    = "${var.prefix}-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id
}

resource "google_compute_subnetwork" "main" {
  name                     = "${var.prefix}-subnet"
  ip_cidr_range            = "10.0.0.0/24"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  project                  = var.project_id
  private_ip_google_access = true
}

# ── Private services access — lets Cloud SQL get a private IP in the VPC ─────
resource "google_compute_global_address" "private_ip_range" {
  name          = "${var.prefix}-sql-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
  project       = var.project_id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
}

# ── VPC Access Connector — lets Cloud Run reach the private VPC ───────────────
# Uses a dedicated /28 IP range (required by GCP — cannot share with main subnet)
resource "google_vpc_access_connector" "connector" {
  name          = "${var.prefix}-connector"
  region        = var.region
  project       = var.project_id
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.8.0.0/28"

  min_instances = 2
  max_instances = 10
  machine_type  = "e2-micro"
}
