from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


_s3_client = boto3.client(
    "s3",
    region_name=os.environ.get("AWS_REGION"),
    config=Config(
        signature_version="s3v4",
        s3={
            "addressing_style": "virtual",
        },
    ),
)


def _bucket_name() -> str:
    return os.environ["DOCUMENTS_BUCKET_NAME"]


def _upload_expires_seconds() -> int:
    return int(os.environ.get("UPLOAD_URL_EXPIRES_SECONDS", "900"))


def _download_expires_seconds() -> int:
    return int(os.environ.get("DOWNLOAD_URL_EXPIRES_SECONDS", "300"))


def _sanitize_file_stem(file_name: str) -> str:
    stem = Path(file_name).stem or "document"
    return re.sub(r"[^A-Za-z0-9._-]", "-", stem)[:80] or "document"


def _build_download_content_disposition(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower() or ".pdf"
    ascii_file_name = f"{_sanitize_file_stem(file_name)}{suffix}"
    utf8_file_name = quote(file_name, safe="")
    return f"inline; filename=\"{ascii_file_name}\"; filename*=UTF-8''{utf8_file_name}"


def generate_document_id() -> str:
    return uuid.uuid4().hex


def build_document_key(
    owner_sub: str,
    document_id: str,
    file_name: str,
    *,
    folder_id: str | None = None,
) -> str:
    safe_stem = _sanitize_file_stem(file_name)
    folder_segment = f"folders/{folder_id}" if folder_id else "root"
    return f"documents/{owner_sub}/{folder_segment}/{document_id}/{safe_stem}.pdf"


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
    url = _s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": _bucket_name(),
            "Key": s3_key,
            "ResponseContentType": "application/pdf",
            "ResponseContentDisposition": _build_download_content_disposition(file_name),
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


def copy_document_object(source_key: str, destination_key: str) -> None:
    _s3_client.copy_object(
        Bucket=_bucket_name(),
        CopySource={
            "Bucket": _bucket_name(),
            "Key": source_key,
        },
        Key=destination_key,
    )


def delete_document_object(s3_key: str) -> None:
    _s3_client.delete_object(Bucket=_bucket_name(), Key=s3_key)
