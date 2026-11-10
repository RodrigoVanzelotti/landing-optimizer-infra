variable "project_id" { type = string }
variable "region" { type = string }
variable "deployment" {
  type = object({
    service_name         = string
    image                = string
    service_account      = string
    cloud_sql_instances  = optional(list(string), [])
    public               = bool
    ingress              = string
    port                 = number
    cpu                  = optional(string, "1")
    memory               = optional(string, "512Mi")
    client               = optional(string)
    client_version       = optional(string)
    revision             = optional(string)
    timeout_seconds      = optional(number, 300)
    max_concurrency      = optional(number, 80)
    cpu_idle             = optional(bool, true)
    startup_cpu_boost    = optional(bool, true)
    invoker_iam_disabled = optional(bool, false)
    service_scaling      = optional(object({ max_instances = number }))
    startup_probe = optional(object({
      failure_threshold = number
      period_seconds    = number
      timeout_seconds   = number
      http_get          = object({ path = string, port = number })
    }))
    traffic = optional(list(object({
      type     = string
      percent  = optional(number, 0)
      revision = optional(string)
      tag      = optional(string)
    })), [{ type = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST", percent = 100 }])
    env        = optional(map(string), {})
    secret_env = optional(map(object({ secret = string, version = string })), {})
    scaling    = object({ min_instances = number, max_instances = number })
  })
}

resource "google_cloud_run_v2_service" "this" {
  project              = var.project_id
  location             = var.region
  name                 = var.deployment.service_name
  deletion_protection  = true
  ingress              = var.deployment.ingress
  invoker_iam_disabled = var.deployment.invoker_iam_disabled
  client               = var.deployment.client
  client_version       = var.deployment.client_version

  dynamic "scaling" {
    for_each = var.deployment.service_scaling == null ? [] : [var.deployment.service_scaling]
    content { max_instance_count = scaling.value.max_instances }
  }

  template {
    dynamic "volumes" {
      for_each = length(var.deployment.cloud_sql_instances) == 0 ? [] : [1]
      content {
        name = "cloudsql"
        cloud_sql_instance { instances = var.deployment.cloud_sql_instances }
      }
    }
    revision                         = var.deployment.revision
    service_account                  = var.deployment.service_account
    timeout                          = "${var.deployment.timeout_seconds}s"
    max_instance_request_concurrency = var.deployment.max_concurrency
    scaling {
      min_instance_count = var.deployment.scaling.min_instances
      max_instance_count = var.deployment.scaling.max_instances
    }
    containers {
      dynamic "volume_mounts" {
        for_each = length(var.deployment.cloud_sql_instances) == 0 ? [] : [1]
        content {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
      image = var.deployment.image
      ports { container_port = var.deployment.port }
      resources {
        limits            = { cpu = var.deployment.cpu, memory = var.deployment.memory }
        cpu_idle          = var.deployment.cpu_idle
        startup_cpu_boost = var.deployment.startup_cpu_boost
      }
      dynamic "startup_probe" {
        for_each = var.deployment.startup_probe == null ? [] : [var.deployment.startup_probe]
        content {
          failure_threshold = startup_probe.value.failure_threshold
          period_seconds    = startup_probe.value.period_seconds
          timeout_seconds   = startup_probe.value.timeout_seconds
          http_get {
            path = startup_probe.value.http_get.path
            port = startup_probe.value.http_get.port
          }
        }
      }
      dynamic "env" {
        for_each = var.deployment.env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = var.deployment.secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret
              version = env.value.version
            }
          }
        }
      }
    }
  }
  dynamic "traffic" {
    for_each = var.deployment.traffic
    content {
      type     = traffic.value.type
      percent  = traffic.value.percent
      revision = traffic.value.revision
      tag      = traffic.value.tag
    }
  }
  lifecycle { prevent_destroy = true }
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.deployment.public ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "uri" { value = google_cloud_run_v2_service.this.uri }
