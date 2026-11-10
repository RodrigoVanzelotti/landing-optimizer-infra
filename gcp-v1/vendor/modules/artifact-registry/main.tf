variable "project_id" { type = string }
variable "region" { type = string }
variable "repository_id" { type = string }

resource "google_artifact_registry_repository" "this" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  format        = "DOCKER"
  lifecycle { prevent_destroy = true }
}
