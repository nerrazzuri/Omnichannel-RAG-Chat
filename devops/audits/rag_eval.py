#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

import requests


def _post(session: requests.Session, url: str, json_body: Dict[str, Any]) -> requests.Response:
    return session.post(url, json=json_body, timeout=10)


def main():
    parser = argparse.ArgumentParser(description="Run simple RAG eval against AI-Core")
    parser.add_argument("--base", default=os.getenv("AI_CORE_URL", "http://localhost:8000"))
    parser.add_argument("--out", default="devops/reports/rag_eval.json")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    s = requests.Session()

    # Health check gate
    try:
        r = s.get(f"{base}/v1/ready", timeout=5)
        r.raise_for_status()
    except Exception:
        print("AI-Core not ready at", f"{base}/v1/ready", file=sys.stderr)
        sys.exit(1)

    tests = [
        {
            "name": "doc_lookup",
            "question": "What is covered in chapter 1?",
        },
        {
            "name": "aggregate_count",
            "question": "How many employees are in Finance?",
        },
        {
            "name": "compare_depts",
            "question": "Compare Finance and Engineering headcount.",
        },
    ]

    out: Dict[str, Any] = {"base": base, "ts": int(time.time()), "results": []}

    # Prefer /v1/rag/ask if available; otherwise fallback to /v1/query
    rag_url = f"{base}/v1/rag/ask"
    query_url = f"{base}/v1/query"
    use_rag = False
    try:
        probe = s.options(rag_url, timeout=5)
        if probe.status_code < 500:
            use_rag = True
    except Exception:
        use_rag = False

    for t in tests:
        q = t["question"]
        try:
            if use_rag:
                body = {
                    "tenantId": "00000000-0000-0000-0000-000000000001",
                    "question": q,
                    "channel": "web",
                    "userId": "00000000-0000-0000-0000-000000000002",
                }
                r = _post(s, rag_url, body)
            else:
                body = {
                    "tenantId": "00000000-0000-0000-0000-000000000001",
                    "message": q,
                    "channel": "web",
                    "userId": "00000000-0000-0000-0000-000000000002",
                }
                r = _post(s, query_url, body)
            ok = r.status_code == 200
            try:
                data = r.json()
            except Exception:
                data = {"raw": r.text}
            out["results"].append(
                {
                    "name": t["name"],
                    "status": r.status_code,
                    "ok": ok,
                    "response": data,
                }
            )
        except Exception as e:
            out["results"].append({"name": t["name"], "ok": False, "error": str(e)})

    # Ensure reports directory exists
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote RAG evaluation to {args.out}")


if __name__ == "__main__":
    main()

