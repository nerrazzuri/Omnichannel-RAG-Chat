# Minimal Vault provider stub and KV v2 mount for ai_core

terraform {
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = ">= 3.25.0"
    }
  }
}

provider "vault" {
  address = var.vault_addr # e.g., https://vault.example.com
  token   = var.vault_token
}

variable "vault_addr" {
  type        = string
  description = "Vault address"
}

variable "vault_token" {
  type        = string
  description = "Vault bootstrap token"
  sensitive   = true
}

# KV v2 enablement (if not already enabled)
resource "vault_mount" "ai_core_kv" {
  path        = "secret"
  type        = "kv-v2"
  description = "AI Core secrets"
}

# Example: initial secrets under secret/data/ai_core
resource "vault_kv_secret_v2" "ai_core" {
  mount = vault_mount.ai_core_kv.path
  name  = "ai_core"
  data_json = jsonencode({
    OPENAI_API_KEY     = "change-me",
    DB_PASSWORD        = "change-me",
    QDRANT_API_KEY     = "",
    REDIS_PASSWORD     = "",
    JWT_SECRET         = "please-set-32-chars-minimum--------------------------------",
    ADMIN_UPLOAD_BEARER = "",
  })
}


