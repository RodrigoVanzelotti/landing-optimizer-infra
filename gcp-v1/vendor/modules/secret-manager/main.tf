variable "project_id" { type = string }
variable "secrets" { type = set(string) }

resource "google_secret_manager_secret" "this" {
  for_each  = var.secrets
  project   = var.project_id
  secret_id = each.value
  replication {
    auto {}
  }
  lifecycle { prevent_destroy = true }
}
