from __future__ import annotations

import base64
import json
from typing import Any


DEFAULT_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
}


def json_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": DEFAULT_HEADERS,
        "body": json.dumps(body, ensure_ascii=False),
    }


def error_response(status_code: int, message: str, *, code: str) -> dict[str, Any]:
    return json_response(
        status_code,
        {
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


def parse_json_body(event: dict[str, Any]) -> dict[str, Any]:
    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")
    return json.loads(raw_body)
