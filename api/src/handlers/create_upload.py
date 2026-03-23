from __future__ import annotations

import os
from typing import Any

from botocore.exceptions import ClientError

from models.document import DocumentRecord
from services.auth import AuthError, get_user_sub
from services.document_repo import create_pending_document, utc_now_iso
from services.folder_repo import get_folder
from services.http import error_response, json_response, parse_json_body
from services.storage import (
    build_document_key,
    create_presigned_upload_url,
    generate_document_id,
)


def _max_upload_bytes() -> int:
    return int(os.environ.get("MAX_PDF_SIZE_BYTES", str(25 * 1024 * 1024)))


def _validate_payload(payload: dict[str, Any]) -> tuple[str, str, int, str | None] | None:
    file_name = str(payload.get("file_name") or "").strip()
    content_type = str(payload.get("content_type") or "").strip().lower()
    file_size = payload.get("file_size")
    folder_id_raw = payload.get("folder_id")
    folder_id = None
    if folder_id_raw is not None:
        if not isinstance(folder_id_raw, str) or not folder_id_raw.strip():
            return None
        folder_id = folder_id_raw.strip()

    if not file_name.lower().endswith(".pdf"):
        return None
    if content_type != "application/pdf":
        return None
    if not isinstance(file_size, int) or file_size <= 0 or file_size > _max_upload_bytes():
        return None

    return file_name, content_type, file_size, folder_id


def handler(event: dict, _context: Any) -> dict:
    try:
        owner_sub = get_user_sub(event)
    except AuthError as error:
        return error_response(401, str(error), code="unauthorized")

    try:
        payload = parse_json_body(event)
    except ValueError:
        return error_response(400, "Request body must be valid JSON.", code="invalid_json")

    validated = _validate_payload(payload)
    if not validated:
        return error_response(
            400,
            "Only PDF files up to the configured size limit are accepted.",
            code="invalid_file",
        )

    file_name, content_type, file_size, folder_id = validated
    if folder_id and not get_folder(owner_sub, folder_id):
        return error_response(400, "Folder not found.", code="invalid_folder_id")

    document_id = generate_document_id()
    now = utc_now_iso()
    s3_key = build_document_key(owner_sub, document_id, file_name, folder_id=folder_id)
    record = DocumentRecord(
        owner_sub=owner_sub,
        document_id=document_id,
        status="pending_upload",
        file_name=file_name,
        content_type=content_type,
        file_size=file_size,
        s3_key=s3_key,
        created_at=now,
        updated_at=now,
        folder_id=folder_id,
    )

    try:
        create_pending_document(record)
    except ClientError:
        return error_response(500, "Failed to create upload session.", code="upload_create_failed")

    upload = create_presigned_upload_url(s3_key, content_type)
    return json_response(
        201,
        {
            "document_id": document_id,
            "status": record.status,
            "folder_id": folder_id,
            "upload_url": upload["url"],
            "upload_method": "PUT",
            "upload_headers": {
                "Content-Type": content_type,
            },
            "expires_in": upload["expires_in"],
        },
    )
