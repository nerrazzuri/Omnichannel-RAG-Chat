terraform {
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = ">= 3.25.0"
    }
  }
}

variable "namespace" { type = string }
variable "k8s_host" { type = string }
variable "k8s_sa_jwt" { type = string }
variable "k8s_ca_crt" { type = string }

# Enable KV v2 at path "kv"
resource "vault_mount" "kv" {
  path        = "kv"
  type        = "kv-v2"
  description = "KV v2 for application secrets"
}

# Policies granting read to ai-core and gateway paths
resource "vault_policy" "ai_core" {
  name   = "ai-core-policy"
  policy = <<EOT
path "kv/data/ai_core/*" {
  capabilities = ["read"]
}
path "kv/data/ai-core/*" {
  capabilities = ["read"]
}
EOT
}

resource "vault_policy" "gateway" {
  name   = "gateway-policy"
  policy = <<EOT
path "kv/data/gateway/*" {
  capabilities = ["read"]
}
EOT
}

# Enable Kubernetes auth
resource "vault_auth_backend" "kubernetes" {
  type = "kubernetes"
}

resource "vault_kubernetes_auth_backend_config" "this" {
  backend            = vault_auth_backend.kubernetes.path
  kubernetes_host    = var.k8s_host
  kubernetes_ca_cert = var.k8s_ca_crt
  token_reviewer_jwt = var.k8s_sa_jwt
}

# Roles mapping k8s service accounts to policies
resource "vault_kubernetes_auth_backend_role" "ai_core" {
  backend                          = vault_auth_backend.kubernetes.path
  role_name                        = "ai-core"
  bound_service_account_names      = ["ai-core"]
  bound_service_account_namespaces = [var.namespace]
  token_policies                   = [vault_policy.ai_core.name]
  token_ttl                        = 86400
  token_max_ttl                    = 259200
}

resource "vault_kubernetes_auth_backend_role" "gateway" {
  backend                          = vault_auth_backend.kubernetes.path
  role_name                        = "gateway"
  bound_service_account_names      = ["gateway"]
  bound_service_account_namespaces = [var.namespace]
  token_policies                   = [vault_policy.gateway.name]
  token_ttl                        = 86400
  token_max_ttl                    = 259200
}

output "kv_path" { value = vault_mount.kv.path }
output "policies" { value = [vault_policy.ai_core.name, vault_policy.gateway.name] }
output "k8s_auth_path" { value = vault_auth_backend.kubernetes.path }


