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


variable "image_gateway" {
  type        = string
  description = "Container image for Gateway"
  default     = "ghcr.io/example/gateway:latest"
}


variable "k8s_host" {
  type        = string
  description = "Kubernetes API server URL"
}

variable "tf_state_bucket" {
  type        = string
  description = "S3 bucket for Terraform remote state"
}

variable "tf_state_lock_table" {
  type        = string
  description = "DynamoDB table for Terraform state locking"
}

variable "aws_region" {
  type        = string
  description = "AWS region for backend and resources"
  default     = "us-east-1"
}

variable "k8s_sa_jwt" {
  type        = string
  description = "Service account JWT for Vault Kubernetes auth"
  sensitive   = true
}

variable "k8s_ca_crt" {
  type        = string
  description = "Kubernetes cluster CA certificate (PEM)"
}

