terraform {
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = ">= 3.20.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.29.0"
    }
  }
}

provider "vault" {
  count   = var.use_vault ? 1 : 0
  address = var.vault_addr
  token   = var.vault_token
}

data "vault_kv_secret_v2" "ai_core" {
  count = var.use_vault ? 1 : 0
  mount = "secret"
  name  = "ai_core"
}

locals {
  db_url_vault    = var.use_vault && length(data.vault_kv_secret_v2.ai_core) > 0 ? lookup(data.vault_kv_secret_v2.ai_core[0].data, "DATABASE_URL", null) : null
  redis_url_vault = var.use_vault && length(data.vault_kv_secret_v2.ai_core) > 0 ? lookup(data.vault_kv_secret_v2.ai_core[0].data, "REDIS_URL", null) : null
}

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.30.0"
    }
  }
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}


