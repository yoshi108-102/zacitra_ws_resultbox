from __future__ import annotations

from typing import Any

from services.auth import AuthError, get_user_sub
from services.document_repo import list_documents
from services.http import error_response, json_response


def handler(event: dict, _context: Any) -> dict:
    try:
        owner_sub = get_user_sub(event)
    except AuthError as error:
        return error_response(401, str(error), code="unauthorized")

    documents = sorted(
        list_documents(owner_sub),
        key=lambda document: document.created_at,
        reverse=True,
    )
    items = [document.to_public_dict() for document in documents]
    return json_response(200, {"items": items})
