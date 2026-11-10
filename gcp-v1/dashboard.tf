variable "dashboard_image" {
  type     = string
  default  = null
  nullable = true
}

resource "google_service_account" "dashboard" {
  account_id   = "landing-optimizer-dashboard-v1"
  display_name = "Landing Optimizer V1 dashboard"
}

module "dashboard" {
  count      = var.dashboard_image == null ? 0 : 1
  source     = "./vendor/modules/cloud-run-service"
  project_id = local.project
  region     = local.region
  deployment = {
    service_name    = "landing-optimizer-dashboard"
    image           = var.dashboard_image
    service_account = google_service_account.dashboard.email
    public          = true
    ingress         = "INGRESS_TRAFFIC_ALL"
    port            = 8080
    cpu             = "1"
    memory          = "512Mi"
    max_concurrency = 20
    scaling         = { min_instances = 0, max_instances = 2 }
    service_scaling = { max_instances = 2 }
    env = {
      NODE_ENV = "production"
      HOSTNAME = "0.0.0.0"
    }
    startup_probe = { failure_threshold = 12, period_seconds = 5, timeout_seconds = 2, http_get = { path = "/login", port = 8080 } }
  }
}

output "dashboard_url" { value = var.dashboard_image == null ? null : module.dashboard[0].uri }
