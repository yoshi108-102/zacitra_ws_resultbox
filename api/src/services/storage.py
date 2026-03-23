from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError


_s3_client = boto3.client("s3")


def _bucket_name() -> str:
    return os.environ["DOCUMENTS_BUCKET_NAME"]


def _upload_expires_seconds() -> int:
    return int(os.environ.get("UPLOAD_URL_EXPIRES_SECONDS", "900"))


def _download_expires_seconds() -> int:
    return int(os.environ.get("DOWNLOAD_URL_EXPIRES_SECONDS", "300"))


def _sanitize_file_stem(file_name: str) -> str:
    stem = Path(file_name).stem or "document"
    return re.sub(r"[^A-Za-z0-9._-]", "-", stem)[:80] or "document"


def generate_document_id() -> str:
    return uuid.uuid4().hex


def build_document_key(owner_sub: str, document_id: str, file_name: str) -> str:
    safe_stem = _sanitize_file_stem(file_name)
    return f"documents/{owner_sub}/{document_id}/{safe_stem}.pdf"


def create_presigned_upload_url(s3_key: str, content_type: str) -> dict[str, Any]:
    url = _s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": _bucket_name(),
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=_upload_expires_seconds(),
    )
    return {
        "url": url,
        "expires_in": _upload_expires_seconds(),
    }


def create_presigned_download_url(s3_key: str, file_name: str) -> dict[str, Any]:
    safe_file_name = file_name.replace('"', "")
    url = _s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": _bucket_name(),
            "Key": s3_key,
            "ResponseContentType": "application/pdf",
            "ResponseContentDisposition": f'inline; filename="{safe_file_name}"',
        },
        ExpiresIn=_download_expires_seconds(),
    )
    return {
        "url": url,
        "expires_in": _download_expires_seconds(),
    }


def head_document(s3_key: str) -> dict[str, Any] | None:
    try:
        return _s3_client.head_object(Bucket=_bucket_name(), Key=s3_key)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
