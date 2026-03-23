from __future__ import annotations

from typing import Any

from services.auth import AuthError, get_user_sub
from services.document_repo import get_document
from services.http import error_response, json_response
from services.storage import create_presigned_download_url


def handler(event: dict, _context: Any) -> dict:
    try:
        owner_sub = get_user_sub(event)
    except AuthError as error:
        return error_response(401, str(error), code="unauthorized")

    document_id = (event.get("pathParameters") or {}).get("document_id")
    if not document_id:
        return error_response(400, "Document ID is required.", code="missing_document_id")

    record = get_document(owner_sub, document_id)
    if not record:
        return error_response(404, "Document not found.", code="not_found")
    if record.status != "ready":
        return error_response(
            409,
            "Document is not ready to download yet.",
            code="document_not_ready",
        )

    download = create_presigned_download_url(record.s3_key, record.file_name)
    return json_response(
        200,
        {
            "document_id": document_id,
            "file_name": record.file_name,
            "download_url": download["url"],
            "expires_in": download["expires_in"],
        },
    )
