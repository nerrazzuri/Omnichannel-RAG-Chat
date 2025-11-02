from __future__ import annotations

import os
import logging
from typing import Optional

from shared.security.vault_client import vault_client
from shared.metrics.vault_metrics import vault_metrics
from ai_core.pipeline.audit_service import write_vault_audit


class SecretManager:
    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        # Prefer Vault when enabled
        try:
            val = vault_client.get_secret(name)
            if val:
                vault_metrics.inc_audit_event()
                try:
                    write_vault_audit(name, None)
                except Exception:
                    pass
                return val
        except Exception as e:
            logging.getLogger(__name__).warning(
                "[secret.fetch] vault fallback for %s", name
            )
        # .env already loaded by app; Docker secrets (file mounts) prefixed with _FILE
        file_var = os.getenv(name + "_FILE")
        if file_var and os.path.isfile(file_var):  # type: ignore
            try:
                with open(file_var, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return os.getenv(name, default)

    def require(self, name: str) -> str:
        val = self.get(name)
        if not val:
            raise RuntimeError(f"Missing required secret: {name}")
        return val


secret_manager = SecretManager()
