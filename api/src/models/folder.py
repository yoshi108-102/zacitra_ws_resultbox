from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def build_folder_sort_key(folder_id: str) -> str:
    return f"folder#{folder_id}"


@dataclass(frozen=True)
class FolderRecord:
    owner_sub: str
    folder_id: str
    folder_name: str
    created_at: str
    updated_at: str
    item_type: str = "folder"

    def to_item(self) -> dict[str, Any]:
        return {
            "owner_sub": self.owner_sub,
            "document_id": build_folder_sort_key(self.folder_id),
            "item_type": self.item_type,
            "folder_id": self.folder_id,
            "folder_name": self.folder_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "FolderRecord":
        folder_id = item.get("folder_id")
        if not folder_id:
            folder_id = str(item["document_id"]).split("folder#", 1)[-1]

        return cls(
            owner_sub=item["owner_sub"],
            folder_id=folder_id,
            folder_name=item["folder_name"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            item_type=item.get("item_type", "folder"),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "folder_id": self.folder_id,
            "folder_name": self.folder_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
