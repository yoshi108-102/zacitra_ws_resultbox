from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from models.folder import FolderRecord
from services.auth import AuthError, get_user_sub
from services.document_repo import utc_now_iso
from services.folder_repo import create_folder, list_folders
from services.http import error_response, json_response, parse_json_body
from services.storage import generate_document_id


def _validate_folder_name(payload: dict[str, Any]) -> str | None:
    folder_name = str(payload.get("folder_name") or "").strip()
    if not folder_name or len(folder_name) > 80:
        return None
    return folder_name


def handler(event: dict, _context: Any) -> dict:
    try:
        owner_sub = get_user_sub(event)
    except AuthError as error:
        return error_response(401, str(error), code="unauthorized")

    try:
        payload = parse_json_body(event)
    except ValueError:
        return error_response(400, "Request body must be valid JSON.", code="invalid_json")

    folder_name = _validate_folder_name(payload)
    if not folder_name:
        return error_response(400, "Folder name is required and must be 80 characters or fewer.", code="invalid_folder")

    existing_names = {folder.folder_name.casefold() for folder in list_folders(owner_sub)}
    if folder_name.casefold() in existing_names:
        return error_response(409, "A folder with the same name already exists.", code="folder_already_exists")

    now = utc_now_iso()
    record = FolderRecord(
        owner_sub=owner_sub,
        folder_id=generate_document_id(),
        folder_name=folder_name,
        created_at=now,
        updated_at=now,
    )

    try:
        create_folder(record)
    except ClientError:
        return error_response(500, "Failed to create folder.", code="folder_create_failed")

    return json_response(201, record.to_public_dict())
