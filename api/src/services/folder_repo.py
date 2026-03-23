from __future__ import annotations

import os

import boto3
from boto3.dynamodb.conditions import Key

from models.folder import FolderRecord, build_folder_sort_key


_dynamodb = boto3.resource("dynamodb")


def _table():
    return _dynamodb.Table(os.environ["DOCUMENTS_TABLE_NAME"])


def _is_folder_item(item: dict) -> bool:
    return item.get("item_type") == "folder"


def create_folder(record: FolderRecord) -> None:
    _table().put_item(
        Item=record.to_item(),
        ConditionExpression="attribute_not_exists(owner_sub) AND attribute_not_exists(document_id)",
    )


def get_folder(owner_sub: str, folder_id: str) -> FolderRecord | None:
    response = _table().get_item(
        Key={
            "owner_sub": owner_sub,
            "document_id": build_folder_sort_key(folder_id),
        }
    )
    item = response.get("Item")
    if not item or not _is_folder_item(item):
        return None
    return FolderRecord.from_item(item)


def list_folders(owner_sub: str) -> list[FolderRecord]:
    response = _table().query(
        KeyConditionExpression=Key("owner_sub").eq(owner_sub),
        ScanIndexForward=False,
    )
    return [
        FolderRecord.from_item(item)
        for item in response.get("Items", [])
        if _is_folder_item(item)
    ]
