from __future__ import annotations

from typing import Any

from services.auth import AuthError, get_user_sub
from services.folder_repo import list_folders
from services.http import error_response, json_response


def handler(event: dict, _context: Any) -> dict:
    try:
        owner_sub = get_user_sub(event)
    except AuthError as error:
        return error_response(401, str(error), code="unauthorized")

    folders = sorted(
        list_folders(owner_sub),
        key=lambda folder: folder.folder_name.casefold(),
    )
    items = [folder.to_public_dict() for folder in folders]
    return json_response(200, {"items": items})
