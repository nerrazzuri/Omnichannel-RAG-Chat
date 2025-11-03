exit_after_auth = false

pid_file = "/tmp/vault-agent.pid"

auto_auth {
  method "token" {
    mount_path = "auth/token"
    config = {
      token = "${VAULT_TOKEN}"
    }
  }
}

vault {
  address = "${VAULT_ADDR}"
}

template {
  source      = "/config/jwt.ctmpl"
  destination = "/out/jwt_secret"
  command     = "chmod 0400 /out/jwt_secret"
}


