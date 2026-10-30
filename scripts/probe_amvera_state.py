"""Readiness and source-failure probe for a dedicated demonstration deployment."""
import argparse
import json
import os
from pathlib import Path

import httpx
from smoke import wait_for


def probe(base_url, offline):
    with httpx.Client(base_url=base_url, timeout=20) as client:
        wait_for(lambda: client.get("/api/health/ready").json(), lambda value: value.get("status") == "ready", 180)
        client.post("/api/auth/login", json={"email": os.environ["E2E_EMAIL"],
                                          "password": os.environ["E2E_PASSWORD"]}).raise_for_status()
        if offline:
            response = client.post("/api/demo", json={"scenario": "outage"})
            assert response.status_code == 503, response.text
            client.post("/api/sources/sync").raise_for_status()
        source = wait_for(lambda: client.get("/api/sources").json(),
                          lambda value: value.get("status") == ("error" if offline else "online"), 90)
        return {"check": "source_unavailable" if offline else "source_recovered",
                "passed": True, "source_status": source["status"],
                "indexed_runbooks": client.get("/api/health/ready").json()["indexed_runbooks"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    result = probe(args.url, args.offline)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
