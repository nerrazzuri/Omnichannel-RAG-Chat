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


