# Freeze the legacy local root while the owner publishes the central workflows.
resource "terraform_data" "centralized" {
  lifecycle {
    precondition {
      condition     = terraform.workspace == "__legacy_root_disabled__"
      error_message = "Cloud infrastructure moved to personal-cloud-infrastructure/solutions/landing-optimizer/terraform/v1. Run Terraform there against the existing V1 backend."
    }
  }
}
