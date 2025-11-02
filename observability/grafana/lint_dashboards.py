from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    base = Path(__file__).resolve().parents[1] / "grafana" / "dashboards"
    errs = 0
    for p in base.glob("*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            # minimal schema checks
            if "title" not in data or "panels" not in data:
                print(f"invalid dashboard: {p}")
                errs += 1
        except Exception as e:
            print(f"failed parsing {p}: {e}")
            errs += 1
    if errs:
        sys.exit(2)


if __name__ == "__main__":
    main()


