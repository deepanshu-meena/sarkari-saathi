"""AWS Lambda entrypoint (API Gateway HTTP API, payload v2) for the deterministic
endpoints. Deploy with `sam build && sam deploy --guided` (see template.yaml)."""
from __future__ import annotations

import json
from typing import Any

from .engine import Profile, find_schemes, load_schemes

_HEADERS = {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}


def _resp(code: int, body: Any) -> dict[str, Any]:
    return {"statusCode": code, "headers": _HEADERS, "body": json.dumps(body, ensure_ascii=False)}


def handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    http = event.get("requestContext", {}).get("http", {})
    method, path = http.get("method", "GET"), event.get("rawPath", "/")
    if method == "GET" and path.endswith("/schemes"):
        return _resp(200, load_schemes())
    if method == "POST" and path.endswith("/eligibility"):
        try:
            payload = json.loads(event.get("body") or "{}")
            return _resp(200, find_schemes(Profile.from_dict(payload)))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return _resp(400, {"error": f"Invalid request: {exc}"})
    return _resp(404, {"error": "Not found"})
