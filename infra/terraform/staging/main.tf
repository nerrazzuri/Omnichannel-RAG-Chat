resource "kubernetes_namespace" "ns" {
  metadata { name = var.namespace }
}

resource "kubernetes_deployment" "ai_core" {
  metadata { name = "ai-core" namespace = var.namespace }
  spec {
    replicas = 1
    selector { match_labels = { app = "ai-core" } }
    template {
      metadata { labels = { app = "ai-core" } }
      spec {
        container {
          name  = "ai-core"
          image = var.image_ai_core
          port { container_port = 8000 }
          env { name = "DATABASE_URL" value = "postgresql://user:password@postgres:5432/omni" }
          env { name = "REDIS_URL" value = "redis://redis:6379/0" }
          env { name = "QDRANT_URL" value = "http://qdrant:6333" }
          liveness_probe {
            http_get { path = "/v1/health" port = 8000 }
            initial_delay_seconds = 10
          }
          readiness_probe {
            http_get { path = "/v1/health" port = 8000 }
            initial_delay_seconds = 5
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "ai_core" {
  metadata { name = "ai-core" namespace = var.namespace }
  spec {
    selector = { app = "ai-core" }
    port { port = 8000 target_port = 8000 }
  }
}

resource "kubernetes_deployment" "frontend" {
  metadata { name = "frontend" namespace = var.namespace }
  spec {
    replicas = 1
    selector { match_labels = { app = "frontend" } }
    template {
      metadata { labels = { app = "frontend" } }
      spec {
        container {
          name  = "frontend"
          image = var.image_frontend
          port { container_port = 3000 }
          env { name = "AI_CORE_URL" value = "http://ai-core:8000" }
          liveness_probe {
            http_get { path = "/" port = 3000 }
            initial_delay_seconds = 10
          }
          readiness_probe {
            http_get { path = "/" port = 3000 }
            initial_delay_seconds = 5
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "frontend" {
  metadata { name = "frontend" namespace = var.namespace }
  spec {
    type = "NodePort"
    selector = { app = "frontend" }
    port { port = 3000 target_port = 3000 node_port = 30080 }
  }
}


