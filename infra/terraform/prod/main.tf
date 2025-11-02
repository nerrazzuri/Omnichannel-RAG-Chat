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

variable "namespace" { type = string default = "omni-prod" }
variable "k8s_host" { type = string }
variable "k8s_sa_jwt" { type = string }
variable "k8s_ca_crt" { type = string }

module "vault" {
  source     = "../modules/vault"
  namespace  = var.namespace
  k8s_host   = var.k8s_host
  k8s_sa_jwt = var.k8s_sa_jwt
  k8s_ca_crt = var.k8s_ca_crt
}

module "gateway" {
  source     = "../modules/gateway"
  namespace  = var.namespace
  vault_path = "kv/gateway"
}

# Backup bucket for prod
module "backup" {
  source        = "../modules/backup"
  bucket_name   = "omni-prod-backups"
  retention_days = 90
  tags = { env = "prod", service = "bdr" }
}


