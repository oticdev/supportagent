output "service_url" {
  value = google_cloud_run_v2_service.backend.uri
}

output "artifact_registry_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Set as GCP_WORKLOAD_IDENTITY_PROVIDER secret in the backend GitHub repo"
}

output "deploy_service_account" {
  value       = google_service_account.github_deploy.email
  description = "Set as GCP_SERVICE_ACCOUNT secret in the backend GitHub repo"
}
