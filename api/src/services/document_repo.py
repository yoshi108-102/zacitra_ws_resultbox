from __future__ import annotations

import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

from models.document import DocumentRecord


_dynamodb = boto3.resource("dynamodb")


def _table():
    return _dynamodb.Table(os.environ["DOCUMENTS_TABLE_NAME"])


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_pending_document(record: DocumentRecord) -> None:
    _table().put_item(
        Item=record.to_item(),
        ConditionExpression="attribute_not_exists(owner_sub) AND attribute_not_exists(document_id)",
    )


def get_document(owner_sub: str, document_id: str) -> DocumentRecord | None:
    response = _table().get_item(
        Key={
            "owner_sub": owner_sub,
            "document_id": document_id,
        }
    )
    item = response.get("Item")
    return DocumentRecord.from_item(item) if item else None


def list_documents(owner_sub: str) -> list[DocumentRecord]:
    response = _table().query(
        KeyConditionExpression=Key("owner_sub").eq(owner_sub),
        ScanIndexForward=False,
    )
    return [DocumentRecord.from_item(item) for item in response.get("Items", [])]


def mark_document_ready(
    owner_sub: str,
    document_id: str,
    *,
    file_size: int,
) -> DocumentRecord:
    updated_at = utc_now_iso()
    response = _table().update_item(
        Key={
            "owner_sub": owner_sub,
            "document_id": document_id,
        },
        ConditionExpression="attribute_exists(owner_sub) AND attribute_exists(document_id)",
        UpdateExpression="SET #status = :status, file_size = :file_size, updated_at = :updated_at",
        ExpressionAttributeNames={
            "#status": "status",
        },
        ExpressionAttributeValues={
            ":status": "ready",
            ":file_size": int(file_size),
            ":updated_at": updated_at,
        },
        ReturnValues="ALL_NEW",
    )
    return DocumentRecord.from_item(response["Attributes"])
