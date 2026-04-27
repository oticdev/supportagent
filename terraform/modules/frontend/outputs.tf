output "bucket_name" {
  value = google_storage_bucket.site.name
}

output "load_balancer_ip" {
  value       = google_compute_global_forwarding_rule.https.ip_address
  description = "Point your domain's A record here"
}

output "workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "Set as GCP_WORKLOAD_IDENTITY_PROVIDER secret in the frontend GitHub repo"
}

output "deploy_service_account" {
  value       = google_service_account.github_deploy.email
  description = "Set as GCP_SERVICE_ACCOUNT secret in the frontend GitHub repo"
}
