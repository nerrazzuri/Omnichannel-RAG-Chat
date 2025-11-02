from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict


class PipelineLogger:
    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        base = os.getenv("PIPELINE_LOG_DIR", "/app/logs/pipeline")
        day = datetime.utcnow().strftime("%Y%m%d")
        dpath = os.path.join(base, day)
        try:
            os.makedirs(dpath, exist_ok=True)
        except Exception:
            pass
        self.fpath = os.path.join(dpath, f"{tenant_id}.log")
        self.mode = os.getenv("LOG_MODE", "compact").lower()

    def emit(self, record: Dict[str, Any]) -> None:
        try:
            record.setdefault("tenant_id", self.tenant_id)
            record.setdefault("timestamp", datetime.utcnow().isoformat())
            with open(self.fpath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass
