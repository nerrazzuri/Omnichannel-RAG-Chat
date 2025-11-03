terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.23.0"
    }
    vault = {
      source  = "hashicorp/vault"
      version = ">= 3.25.0"
    }
  }
}

variable "namespace" { type = string }
variable "vault_path" { type = string }
variable "image" { type = string default = "nerrazzuri/omnichannel-gateway:latest" }

data "vault_generic_secret" "gateway" {
  path = var.vault_path
}

resource "kubernetes_deployment" "gateway" {
  metadata {
    name      = "gateway"
    namespace = var.namespace
    labels = { app = "gateway", tier = "api" }
  }
  spec {
    replicas = 2
    selector { match_labels = { app = "gateway" } }
    template {
      metadata {
        labels = { app = "gateway", tier = "api" }
      }
      spec {
        container {
          name  = "gateway"
          image = var.image
          port { container_port = 3001 }
          env {
            name  = "JWT_SECRET"
            value = try(data.vault_generic_secret.gateway.data["JWT_SECRET"], "")
          }
          env {
            name  = "AI_CORE_URL"
            value = try(data.vault_generic_secret.gateway.data["AI_CORE_URL"], "http://ai-core:8000")
          }
          liveness_probe {
            http_get {
              path = "/api/health"
              port = 3001
            }
            initial_delay_seconds = 10
            period_seconds        = 30
          }
          readiness_probe {
            http_get {
              path = "/api/ready"
              port = 3001
            }
            initial_delay_seconds = 10
            period_seconds        = 15
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "gateway" {
  metadata { name = "gateway" namespace = var.namespace labels = { app = "gateway" } }
  spec {
    selector = { app = "gateway" }
    port { name = "http" port = 3001 target_port = 3001 }
    type = "ClusterIP"
  }
}

resource "kubernetes_horizontal_pod_autoscaler_v2" "gateway" {
  metadata { name = "gateway-hpa" namespace = var.namespace }
  spec {
    min_replicas = 2
    max_replicas = 6
    scale_target_ref { api_version = "apps/v1" kind = "Deployment" name = kubernetes_deployment.gateway.metadata[0].name }
    metric {
      type = "Resource"
      resource { name = "cpu" target { type = "Utilization" average_utilization = 70 } }
    }
  }
}

output "gateway_url" { value = "http://${kubernetes_service.gateway.metadata[0].name}:3001" }
output "gateway_replicas" { value = kubernetes_deployment.gateway.spec[0].replicas }
output "gateway_hpa_status" { value = kubernetes_horizontal_pod_autoscaler_v2.gateway.status }


