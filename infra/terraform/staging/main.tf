# Gateway module
module "gateway" {
  source     = "../modules/gateway"
  namespace  = "omnichannel"
  vault_path = "kv/gateway"
}

# Vault module
module "vault" {
  source    = "../modules/vault"
  namespace = "omnichannel"
  k8s_host  = var.k8s_host
  k8s_sa_jwt = var.k8s_sa_jwt
  k8s_ca_crt = var.k8s_ca_crt
}

# Backup bucket for staging
module "backup" {
  source       = "../modules/backup"
  bucket_name  = "omni-staging-backups"
  retention_days = 30
  tags = { env = "staging", service = "bdr" }
}
resource "kubernetes_namespace" "ns" {
  metadata {
    name = var.namespace
  }
}

resource "kubernetes_deployment" "ai_core" {
  metadata {
    name      = "ai-core"
    namespace = var.namespace
  }
  spec {
    replicas = 1
    selector {
      match_labels = { app = "ai-core" }
    }
    template {
      metadata {
        labels = { app = "ai-core" }
      }
      spec {
        container {
          name  = "ai-core"
          image = var.image_ai_core
          port {
            container_port = 8000
          }
          env {
            name  = "DATABASE_URL"
            value = var.db_url
          }
          env {
            name  = "REDIS_URL"
            value = var.redis_url
          }
          env {
            name  = "QDRANT_URL"
            value = "http://qdrant:6333"
          }
          liveness_probe {
            http_get {
              path = "/v1/health"
              port = 8000
            }
            initial_delay_seconds = 10
          }
          readiness_probe {
            http_get {
              path = "/v1/ready"
              port = 8000
            }
            initial_delay_seconds = 5
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "ai_core" {
  metadata {
    name      = "ai-core"
    namespace = var.namespace
  }
  spec {
    selector = { app = "ai-core" }
    port {
      port        = 8000
      target_port = 8000
    }
  }
}

resource "kubernetes_deployment" "frontend" {
  metadata {
    name      = "frontend"
    namespace = var.namespace
  }
  spec {
    replicas = 1
    selector {
      match_labels = { app = "frontend" }
    }
    template {
      metadata {
        labels = { app = "frontend" }
      }
      spec {
        container {
          name  = "frontend"
          image = var.image_frontend
          port {
            container_port = 3000
          }
          env {
            name  = "AI_CORE_URL"
            value = "http://ai-core:8000"
          }
          liveness_probe {
            http_get {
              path = "/"
              port = 3000
            }
            initial_delay_seconds = 10
          }
          readiness_probe {
            http_get {
              path = "/"
              port = 3000
            }
            initial_delay_seconds = 5
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "frontend" {
  metadata {
    name      = "frontend"
    namespace = var.namespace
  }
  spec {
    type = "NodePort"
    selector = { app = "frontend" }
    port {
      port        = 3000
      target_port = 3000
      node_port   = 30080
    }
  }
}


resource "kubernetes_deployment" "gateway" {
  metadata {
    name      = "gateway"
    namespace = var.namespace
  }
  spec {
    replicas = 2
    selector {
      match_labels = { app = "gateway" }
    }
    template {
      metadata {
        labels = { app = "gateway" }
      }
      spec {
        container {
          name  = "gateway"
          image = var.image_gateway
          port {
            container_port = 3001
          }
          env {
            name  = "AI_CORE_URL"
            value = "http://ai-core:8000"
          }
          env {
            name = "JWT_SECRET"
            value_from {
              secret_key_ref {
                name = "omni-secrets"
                key  = "jwt-secret"
              }
            }
          }
          readiness_probe {
            http_get {
              path = "/api/ready"
              port = 3001
            }
            initial_delay_seconds = 5
          }
          liveness_probe {
            http_get {
              path = "/api/health"
              port = 3001
            }
            initial_delay_seconds = 10
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "gateway" {
  metadata {
    name      = "gateway"
    namespace = var.namespace
  }
  spec {
    selector = { app = "gateway" }
    port {
      port        = 3001
      target_port = 3001
    }
  }
}

