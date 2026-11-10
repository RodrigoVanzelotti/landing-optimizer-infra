terraform {
  required_version = ">= 1.16, < 2.0"
  required_providers {
    google = { source = "hashicorp/google", version = "7.46.2" }
  }
  backend "gcs" {
    bucket = "landing-optimizer-v1-tfstate-505424813528"
    prefix = "landing-optimizer/v1"
  }
}
provider "google" {
  project = local.project
  region  = local.region
}
variable "image" {
  type     = string
  default  = null
  nullable = true
}
variable "deploy_api" {
  type    = bool
  default = false
}
locals {
  project  = "landing-optimizer-landing-page"
  region   = "southamerica-east1"
  base_url = "https://landing-optimizer-api-505424813528.southamerica-east1.run.app"
  secrets  = toset(["lo-v1-database-url", "lo-v1-jwt-secret", "lo-v1-config-key", "lo-v1-operator-password", "lo-v1-ai-token"])
  secret_env = {
    DATABASE_URL          = { secret = "lo-v1-database-url", version = "1" }
    JWT_SECRET            = { secret = "lo-v1-jwt-secret", version = "1" }
    CONFIG_ENCRYPTION_KEY = { secret = "lo-v1-config-key", version = "1" }
    AI_SERVICE_TOKEN      = { secret = "lo-v1-ai-token", version = "1" }
  }
}
resource "google_service_account" "api" {
  account_id   = "landing-optimizer-api-v1"
  display_name = "Landing Optimizer V1 API"
}
resource "google_project_iam_member" "sql_client" {
  project = local.project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}
module "artifacts" {
  source        = "./vendor/modules/artifact-registry"
  project_id    = local.project
  region        = local.region
  repository_id = "landing-optimizer-v1"
}
module "secrets" {
  source     = "./vendor/modules/secret-manager"
  project_id = local.project
  secrets    = local.secrets
}
resource "google_secret_manager_secret_iam_member" "api" {
  for_each   = toset(["lo-v1-database-url", "lo-v1-jwt-secret", "lo-v1-config-key", "lo-v1-ai-token"])
  project    = local.project
  secret_id  = each.value
  role       = "roles/secretmanager.secretAccessor"
  member     = "serviceAccount:${google_service_account.api.email}"
  depends_on = [module.secrets]
}
resource "google_sql_database_instance" "postgres" {
  name                = "landing-optimizer-v1"
  region              = local.region
  database_version    = "POSTGRES_16"
  deletion_protection = true
  settings {
    tier                        = "db-f1-micro"
    edition                     = "ENTERPRISE"
    availability_type           = "ZONAL"
    disk_type                   = "PD_SSD"
    disk_size                   = 10
    disk_autoresize             = true
    disk_autoresize_limit       = 20
    deletion_protection_enabled = true
    backup_configuration {
      enabled                        = true
      start_time                     = "04:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
      backup_retention_settings { retained_backups = 7 }
    }
    ip_configuration { ipv4_enabled = true }
  }
  lifecycle { prevent_destroy = true }
}
resource "google_sql_database" "app" {
  name     = "landing_optimizer"
  instance = google_sql_database_instance.postgres.name
  lifecycle { prevent_destroy = true }
}
resource "google_cloud_run_v2_job" "migrate" {
  count               = var.image == null ? 0 : 1
  name                = "landing-optimizer-migrate-v1"
  location            = local.region
  deletion_protection = true
  template {
    template {
      service_account = google_service_account.api.email
      max_retries     = 0
      timeout         = "300s"
      volumes {
        name = "cloudsql"
        cloud_sql_instance { instances = [google_sql_database_instance.postgres.connection_name] }
      }
      containers {
        image   = var.image
        command = ["node", "node_modules/prisma/build/index.js"]
        args    = ["migrate", "deploy"]
        resources { limits = { cpu = "1", memory = "512Mi" } }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = "lo-v1-database-url"
              version = "1"
            }
          }
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.api, google_project_iam_member.sql_client]
}
module "api" {
  count      = var.deploy_api ? 1 : 0
  source     = "./vendor/modules/cloud-run-service"
  project_id = local.project
  region     = local.region
  deployment = {
    service_name        = "landing-optimizer-api"
    image               = var.image
    service_account     = google_service_account.api.email
    public              = true
    ingress             = "INGRESS_TRAFFIC_ALL"
    port                = 8080
    cpu                 = "1"
    memory              = "512Mi"
    max_concurrency     = 20
    scaling             = { min_instances = 0, max_instances = 2 }
    service_scaling     = { max_instances = 2 }
    cloud_sql_instances = [google_sql_database_instance.postgres.connection_name]
    startup_probe       = { failure_threshold = 12, period_seconds = 5, timeout_seconds = 2, http_get = { path = "/health", port = 8080 } }
    env = {
      NODE_ENV          = "production"
      ANALYTICS_BACKEND = "postgres"
      CDN_SDK_BASE_URL  = "${local.base_url}/v1/sdk"
      INGEST_URL        = "${local.base_url}/v1/events"
      CONFIG_URL        = "${local.base_url}/v1/config"
      AI_SERVICE_URL    = "https://landing-optimizer-ai-505424813528.southamerica-east1.run.app"
    }
    secret_env = local.secret_env
  }
  depends_on = [google_secret_manager_secret_iam_member.api, google_project_iam_member.sql_client]
}
output "api_url" { value = var.deploy_api ? module.api[0].uri : null }
output "database_connection" { value = google_sql_database_instance.postgres.connection_name }
