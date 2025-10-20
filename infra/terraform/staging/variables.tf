variable "namespace" {
  type        = string
  description = "Kubernetes namespace for staging"
  default     = "omni-staging"
}

variable "kubeconfig_path" {
  type        = string
  description = "Path to kubeconfig"
  default     = "~/.kube/config"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "staging"
}

variable "image_ai_core" {
  type        = string
  description = "Container image for AI Core"
  default     = "ghcr.io/example/ai-core:latest"
}

variable "image_frontend" {
  type        = string
  description = "Container image for Frontend"
  default     = "ghcr.io/example/frontend:latest"
}


