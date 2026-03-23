from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from services.auth import AuthError, get_user_sub
from services.document_repo import delete_document_record, get_document
from services.http import error_response, json_response
from services.storage import delete_document_object


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

    try:
        delete_document_object(record.s3_key)
    except ClientError:
        return error_response(500, "Failed to delete document from storage.", code="document_delete_failed")

    try:
        delete_document_record(owner_sub, document_id)
    except ClientError:
        return error_response(500, "Failed to delete document metadata.", code="document_delete_failed")

    return json_response(200, {"document_id": document_id, "deleted": True})
