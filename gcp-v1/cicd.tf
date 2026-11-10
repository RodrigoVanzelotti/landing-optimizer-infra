resource "google_service_account" "deployer" {
  account_id   = "landing-optimizer-deployer"
  display_name = "Landing Optimizer GitHub deployments"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "landing-optimizer-github"
  display_name              = "Landing Optimizer GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
  }
  attribute_condition = "assertion.repository_owner_id == '85701210' && assertion.repository_id in ['1289468641', '1289472289', '1289484739'] && assertion.ref == 'refs/heads/main' && assertion.event_name in ['push', 'workflow_dispatch']"
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

resource "google_service_account_iam_member" "github" {
  for_each           = toset(["1289468641", "1289472289", "1289484739"])
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${each.value}"
}

resource "google_project_iam_member" "deployer" {
  for_each = toset(["roles/viewer", "roles/run.admin", "roles/secretmanager.viewer", "roles/iam.workloadIdentityPoolViewer", "roles/iam.securityReviewer"])
  project  = local.project
  role     = each.value
  member   = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_storage_bucket_iam_member" "deployer" {
  bucket = "landing-optimizer-v1-tfstate-505424813528"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_artifact_registry_repository_iam_member" "deployer" {
  project    = local.project
  location   = local.region
  repository = "landing-optimizer-v1"
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
  depends_on = [module.artifacts]
}

resource "google_service_account_iam_member" "runtime" {
  for_each = {
    api       = google_service_account.api.name
    dashboard = google_service_account.dashboard.name
    ai        = google_service_account.ai.name
  }
  service_account_id = each.value
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
