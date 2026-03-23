from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from services.auth import AuthError, get_user_sub
from services.document_repo import get_document, update_document_location
from services.folder_repo import get_folder
from services.http import error_response, json_response, parse_json_body
from services.storage import build_document_key, copy_document_object, delete_document_object


def _parse_destination_folder_id(payload: dict[str, Any]) -> str | None:
    folder_id = payload.get("folder_id")
    if folder_id is None:
        return None
    if not isinstance(folder_id, str):
        raise ValueError

    normalized = folder_id.strip()
    return normalized or None


def handler(event: dict, _context: Any) -> dict:
    try:
        owner_sub = get_user_sub(event)
    except AuthError as error:
        return error_response(401, str(error), code="unauthorized")

    document_id = (event.get("pathParameters") or {}).get("document_id")
    if not document_id:
        return error_response(400, "Document ID is required.", code="missing_document_id")

    try:
        payload = parse_json_body(event)
    except ValueError:
        return error_response(400, "Request body must be valid JSON.", code="invalid_json")

    try:
        destination_folder_id = _parse_destination_folder_id(payload)
    except ValueError:
        return error_response(400, "Folder ID must be a string or null.", code="invalid_folder_id")

    record = get_document(owner_sub, document_id)
    if not record:
        return error_response(404, "Document not found.", code="not_found")
    if record.status != "ready":
        return error_response(409, "Only ready documents can be moved.", code="document_not_ready")

    if destination_folder_id and not get_folder(owner_sub, destination_folder_id):
        return error_response(400, "Folder not found.", code="invalid_folder_id")

    if destination_folder_id == record.folder_id:
        return json_response(200, record.to_public_dict())

    destination_key = build_document_key(
        owner_sub,
        document_id,
        record.file_name,
        folder_id=destination_folder_id,
    )

    try:
        copy_document_object(record.s3_key, destination_key)
        delete_document_object(record.s3_key)
    except ClientError:
        try:
            delete_document_object(destination_key)
        except ClientError:
            pass
        return error_response(500, "Failed to move document in storage.", code="document_move_failed")

    try:
        updated = update_document_location(
            owner_sub,
            document_id,
            s3_key=destination_key,
            folder_id=destination_folder_id,
        )
    except ClientError:
        try:
            copy_document_object(destination_key, record.s3_key)
            delete_document_object(destination_key)
        except ClientError:
            pass
        return error_response(500, "Failed to update document location.", code="document_move_failed")

    return json_response(200, updated.to_public_dict())
