output "vpc_id" {
  value = google_compute_network.vpc.id
}

output "vpc_name" {
  value = google_compute_network.vpc.name
}

output "connector_id" {
  value = google_vpc_access_connector.connector.id
}

output "private_vpc_connection" {
  description = "Used by Cloud SQL module to ensure peering is established before DB creation"
  value       = google_service_networking_connection.private_vpc.id
}
