variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging|production)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "app_domain" {
  description = "Public dashboard/app domain"
  type        = string
  default     = "app.landingoptimizer.io"
}

variable "api_domain" {
  description = "Public API domain"
  type        = string
  default     = "api.landingoptimizer.io"
}
