# Generate 48 random bytes (Base64 ≈ 64 chars)
$jwt = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))

# Set Vault env (adjust as needed)
$env:VAULT_ADDR = "http://localhost:8200"
$env:VAULT_TOKEN = "<your-root-or-approp-token>"

# Write to KV v2 (CLI handles v2 automatically)
vault kv put secret/gateway JWT_SECRET="$jwt"
vault kv put secret/ai_core JWT_SECRET="$jwt"

# Verify
vault kv get -field=JWT_SECRET secret/gateway
vault kv get -field=JWT_SECRET secret/ai_core