variable "ai_image" {
  type     = string
  default  = null
  nullable = true
}

resource "google_service_account" "ai" {
  account_id   = "landing-optimizer-ai-v1"
  display_name = "Landing Optimizer V1 AI"
}

resource "google_secret_manager_secret_iam_member" "ai" {
  project    = local.project
  secret_id  = "lo-v1-ai-token"
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.ai.email}"
  depends_on = [module.secrets]
}

module "ai" {
  count      = var.ai_image == null ? 0 : 1
  source     = "./vendor/modules/cloud-run-service"
  project_id = local.project
  region     = local.region
  deployment = {
    service_name    = "landing-optimizer-ai"
    image           = var.ai_image
    service_account = google_service_account.ai.email
    public          = true
    ingress         = "INGRESS_TRAFFIC_ALL"
    port            = 8000
    cpu             = "1"
    memory          = "512Mi"
    max_concurrency = 10
    scaling         = { min_instances = 0, max_instances = 2 }
    service_scaling = { max_instances = 2 }
    env = {
      NODE_ENV     = "production"
      LLM_PROVIDER = "stub"
    }
    secret_env    = { INTERNAL_TOKEN = { secret = "lo-v1-ai-token", version = "1" } }
    startup_probe = { failure_threshold = 12, period_seconds = 5, timeout_seconds = 2, http_get = { path = "/health", port = 8000 } }
  }
  depends_on = [google_secret_manager_secret_iam_member.ai]
}

output "ai_url" { value = var.ai_image == null ? null : module.ai[0].uri }
