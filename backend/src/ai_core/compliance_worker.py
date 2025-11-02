from __future__ import annotations

import time
from typing import Dict
from shared.database.session import SessionLocal
from shared.config.tuning import compliance as compliance_cfg
from shared.metrics.compliance_metrics import compliance_metrics
from shared.utils.log_and_continue import log_and_continue
from ai_core.services.compliance_reporter import ComplianceReporter


def loop(stop_flag: Dict[str, bool]) -> None:
    reporter = ComplianceReporter()
    while not stop_flag.get("stop"):
        s = SessionLocal()
        try:
            try:
                # For demo: generate for default tenant
                reporter.generate_for_tenant(
                    s, "00000000-0000-0000-0000-000000000001"
                )
            except Exception as e:
                try:
                    compliance_metrics.inc_failed()
                except Exception:
                    pass
                log_and_continue(e, "compliance.generate", None, None)
        finally:
            try:
                s.close()
            except Exception:
                pass
        # Sleep respecting stop flag
        for _ in range(max(60, int(compliance_cfg.schedule_interval_s))):
            if stop_flag.get("stop"):
                break
            time.sleep(1)


