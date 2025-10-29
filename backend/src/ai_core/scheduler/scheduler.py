from __future__ import annotations

import threading
import time
from typing import List

from shared.config.tuning import connectors
from ai_core.connectors.registry import registry
from ai_core.connectors.sharepoint import SharePointConnector
from ai_core.connectors.googledrive import GoogleDriveConnector
from ai_core.connectors.salesforce import SalesforceConnector


# Register built-in connectors
registry.register(SharePointConnector.name, SharePointConnector)
registry.register(GoogleDriveConnector.name, GoogleDriveConnector)
registry.register(SalesforceConnector.name, SalesforceConnector)


class ConnectorScheduler:
    def __init__(self, tenants: List[str]) -> None:
        self._stop = False
        self._tenants = tenants
        self._interval = connectors.default_interval_s
        # Parse enabled names
        self._names = [n.strip() for n in connectors.enabled_names.split(',') if n.strip()]

    def stop(self) -> None:
        self._stop = True

    def loop(self) -> None:
        if not connectors.enabled or not connectors.scheduler_enabled:
            return
        while not self._stop:
            start = time.time()
            for tenant in self._tenants:
                for name in self._names:
                    cls = registry.get(name)
                    if not cls:
                        continue
                    try:
                        c = cls(tenant)
                        c.run_sync()
                    except Exception:
                        # Silent; metrics already updated in connector
                        pass
            elapsed = time.time() - start
            sleep_s = max(1.0, self._interval - elapsed)
            time.sleep(sleep_s)


