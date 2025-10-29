from __future__ import annotations

import os
from typing import Optional


class SecretManager:
    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
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


