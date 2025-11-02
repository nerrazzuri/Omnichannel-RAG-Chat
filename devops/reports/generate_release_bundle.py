from __future__ import annotations

import os
import json
import time
import shutil
from pathlib import Path
from typing import Any, Dict

import requests


def _get(api: str, path: str, bearer: str | None = None) -> Any:
    headers = {"Accept": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    r = requests.get(api.rstrip("/") + path, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def _post(api: str, path: str, payload: Dict[str, Any], bearer: str | None = None) -> Any:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    r = requests.post(api.rstrip("/") + path, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> None:
    api = os.environ.get("API_BASE", "http://localhost:8000")
    bearer = os.environ.get("ADMIN_UPLOAD_BEARER")
    tenant = os.environ.get("TENANT_ID", "00000000-0000-0000-0000-000000000001")
    out_dir = Path("artifacts/release_audit_bundle")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Compliance summary (ensure latest)
    try:
      _post(api, "/v1/admin/reports/generate", {"tenant_id": tenant}, bearer)
    except Exception:
      pass
    comp = _get(api, f"/v1/admin/reports/latest?tenant_id={tenant}", bearer)
    (out_dir / "compliance_summary.json").write_text(json.dumps(comp, indent=2))

    # 2) Retention summary (basic status)
    try:
        ret = _get(api, f"/v1/admin/retention/status", bearer)
    except Exception:
        ret = {"detail": "unavailable"}
    (out_dir / "retention_summary.json").write_text(json.dumps(ret, indent=2))

    # 3) Backup/restore snapshot: scrape /metrics quick sample
    backup_report = {}
    try:
        m = requests.get(api.rstrip("/") + "/metrics", timeout=20).text
        # Keep a compact metrics snapshot
        (out_dir / "metrics_snapshot.prom").write_text(m)
        # Lightweight parse for backup/restore
        def _val(name: str) -> float:
            for line in m.splitlines():
                if line.startswith(name + " "):
                    try:
                        return float(line.split()[-1])
                    except Exception:
                        pass
            return 0.0
        backup_report = {
            "backup_last_success_unixtime": {
                "postgres": None,
                "redis": None,
                "qdrant": None,
                "vault": None,
            },
            "restore": {
                "duration_seconds": int(_val("restore_drill_duration_seconds")),
                "rto_compliance": int(_val("restore_rto_compliance")) == 1,
                "rpo_compliance": int(_val("restore_rpo_compliance")) == 1,
            },
        }
        # Per system backups if present
        for sys in ("postgres", "redis", "qdrant", "vault"):
            key = f'backup_last_success_unixtime{{system="{sys}"}}'
            for line in m.splitlines():
                if line.startswith(key):
                    try:
                        backup_report["backup_last_success_unixtime"][sys] = int(float(line.split()[-1]))
                    except Exception:
                        backup_report["backup_last_success_unixtime"][sys] = None
        (out_dir / "backup_restore_report.json").write_text(json.dumps(backup_report, indent=2))
    except Exception as e:
        (out_dir / "metrics_snapshot.prom").write_text(f"error: {e}\n")

    # 4) Terraform parity diff – if CI drops it into artifacts/ (optional)
    tf_parity = Path("artifacts/terraform_parity.diff")
    if tf_parity.exists():
        shutil.copy(str(tf_parity), out_dir / "terraform_parity.diff")

    print(f"Release audit bundle written to: {out_dir}")


if __name__ == "__main__":
    main()


