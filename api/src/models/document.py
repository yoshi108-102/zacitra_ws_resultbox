from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DocumentRecord:
    owner_sub: str
    document_id: str
    status: str
    file_name: str
    content_type: str
    file_size: int
    s3_key: str
    created_at: str
    updated_at: str

    def to_item(self) -> dict[str, Any]:
        return {
            "owner_sub": self.owner_sub,
            "document_id": self.document_id,
            "status": self.status,
            "file_name": self.file_name,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "s3_key": self.s3_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> "DocumentRecord":
        return cls(
            owner_sub=item["owner_sub"],
            document_id=item["document_id"],
            status=item["status"],
            file_name=item["file_name"],
            content_type=item["content_type"],
            file_size=int(item["file_size"]),
            s3_key=item["s3_key"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "status": self.status,
            "file_name": self.file_name,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
