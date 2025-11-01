from prometheus_client import Counter, Gauge


class _VaultRotationMetrics:
    def __init__(self) -> None:
        self._token_renew_success = Counter("vault_token_renew_success_total", "Vault token renew successes")
        self._token_renew_failure = Counter("vault_token_renew_failure_total", "Vault token renew failures")
        self._token_ttl_seconds = Gauge("vault_token_ttl_seconds", "Current Vault token TTL in seconds")
        self._rotation_alerts = Counter("vault_rotation_alerts_total", "Rotation alerts triggered when TTL below threshold")
        self._secret_verify_success = Counter("vault_secret_verify_success_total", "Secret verification successes after renewal")
        self._secret_verify_failure = Counter("vault_secret_verify_failure_total", "Secret verification failures after renewal")

    def set_ttl(self, ttl_s: int) -> None:
        self._token_ttl_seconds.set(max(0, int(ttl_s)))

    def inc_renew_ok(self) -> None:
        self._token_renew_success.inc()

    def inc_renew_fail(self) -> None:
        self._token_renew_failure.inc()

    def inc_alert(self) -> None:
        self._rotation_alerts.inc()

    def inc_verify_ok(self) -> None:
        self._secret_verify_success.inc()

    def inc_verify_fail(self) -> None:
        self._secret_verify_failure.inc()


vault_rotation_metrics = _VaultRotationMetrics()


