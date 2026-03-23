from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from services.auth import AuthError, get_user_sub
from services.document_repo import get_document, mark_document_ready
from services.http import error_response, json_response
from services.storage import head_document


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
    if record.status == "ready":
        return json_response(200, record.to_public_dict())

    metadata = head_document(record.s3_key)
    if not metadata:
        return error_response(
            409,
            "Upload has not completed in S3 yet.",
            code="upload_not_found",
        )

    content_type = str(metadata.get("ContentType") or "").lower()
    if content_type != "application/pdf":
        return error_response(400, "Uploaded object is not a PDF.", code="invalid_content_type")

    try:
        updated = mark_document_ready(
            owner_sub,
            document_id,
            file_size=int(metadata.get("ContentLength", 0)),
        )
    except ClientError:
        return error_response(500, "Failed to finalize upload.", code="complete_failed")

    return json_response(200, updated.to_public_dict())
