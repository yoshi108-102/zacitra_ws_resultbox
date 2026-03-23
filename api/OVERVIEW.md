# API 概要

PDF ドキュメントのアップロード・管理を行うサーバーレス API。
AWS Lambda + API Gateway + DynamoDB + S3 で構成される。

---

## ディレクトリ構成

```
api/
├── pyproject.toml          # プロジェクト設定・依存関係
└── src/
    ├── models/
    │   └── document.py     # DocumentRecord データクラス
    ├── handlers/
    │   ├── create_upload.py       # POST /uploads
    │   ├── complete_upload.py     # POST /documents/{id}/complete
    │   ├── list_documents.py      # GET  /documents
    │   └── get_download_url.py    # GET  /documents/{id}/download-url
    └── services/
        ├── auth.py           # JWT 認証 (Cognito)
        ├── document_repo.py  # DynamoDB アクセス
        ├── storage.py        # S3 アクセス・Presigned URL 生成
        └── http.py           # レスポンスユーティリティ
```

---

## 技術スタック

| 技術 | 用途 |
|------|------|
| Python 3.12 | Lambda ランタイム |
| boto3 | AWS SDK (S3 / DynamoDB) |
| AWS Lambda | 実行環境 |
| AWS API Gateway v2 (HTTP API) | エンドポイント公開 |
| AWS DynamoDB | ドキュメントメタデータ保存 |
| AWS S3 | PDF ファイル保存 |
| AWS Cognito | JWT 認証 |

外部ライブラリは `boto3` のみ。フレームワーク不使用。

---

## エンドポイント一覧

| メソッド | パス | ハンドラー | 説明 |
|---------|------|-----------|------|
| `POST` | `/uploads` | `handlers.create_upload` | アップロード開始。Presigned PUT URL を返す |
| `POST` | `/documents/{document_id}/complete` | `handlers.complete_upload` | S3 へのアップロード完了を確認し、ステータスを `ready` に更新 |
| `GET` | `/documents` | `handlers.list_documents` | 自分のドキュメント一覧取得（新しい順） |
| `GET` | `/documents/{document_id}/download-url` | `handlers.get_download_url` | ダウンロード用 Presigned GET URL を取得 |

すべてのエンドポイントで Cognito JWT 認証が必須。

---

## PDFアップロードのフロー

```
クライアント                      API                       AWS
   │                              │                          │
   │  POST /uploads               │                          │
   │  { file_name, content_type,  │                          │
   │    file_size }               │                          │
   │──────────────────────────────▶                          │
   │                              │  DynamoDB PutItem        │
   │                              │  (status: pending_upload)│
   │                              │─────────────────────────▶│
   │                              │  S3 Presigned PUT URL 生成│
   │                              │─────────────────────────▶│
   │  { upload_url, document_id } │                          │
   │◀──────────────────────────────                          │
   │                              │                          │
   │  PUT {upload_url}  (PDF)     │                          │
   │─────────────────────────────────────────────────────────▶
   │                              │                          │
   │  POST /documents/{id}/complete                          │
   │──────────────────────────────▶                          │
   │                              │  S3 HEAD (存在確認)      │
   │                              │─────────────────────────▶│
   │                              │  DynamoDB UpdateItem     │
   │                              │  (status: ready)         │
   │                              │─────────────────────────▶│
   │  { status: "ready", ... }    │                          │
   │◀──────────────────────────────                          │
```

---

## データモデル

### DocumentRecord (`models/document.py`)

DynamoDB テーブルおよびアプリ内で使われるドキュメントの中心モデル。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `owner_sub` | str | Cognito ユーザー ID（パーティションキー） |
| `document_id` | str | UUID hex（ソートキー） |
| `status` | str | `pending_upload` / `ready` |
| `file_name` | str | 元のファイル名 |
| `content_type` | str | 常に `application/pdf` |
| `file_size` | int | バイト数 |
| `s3_key` | str | S3 オブジェクトキー |
| `created_at` | str | ISO 8601 |
| `updated_at` | str | ISO 8601 |

`to_public_dict()` で `owner_sub` と `s3_key` を除いた公開向けの辞書を返す。

### ドキュメントのステート遷移

```
pending_upload  ──[POST /complete]──▶  ready
```

### S3 オブジェクトキーの形式

```
documents/{owner_sub}/{document_id}/{sanitized_file_name}.pdf
```

ファイル名は特殊文字を `-` に置換し、最大80文字に切り詰める。

---

## 各サービス層の役割

### `services/auth.py`
API Gateway イベントの `requestContext.authorizer.jwt.claims` から `sub`（Cognito ユーザー ID）を取得する。認証失敗時は `AuthError` を送出。

### `services/document_repo.py`
DynamoDB に対する CRUD 操作を提供する。

| 関数 | 操作 |
|------|------|
| `create_pending_document(record)` | PutItem（重複防止条件付き） |
| `get_document(owner_sub, document_id)` | GetItem |
| `list_documents(owner_sub)` | Query（降順） |
| `mark_document_ready(owner_sub, document_id, file_size)` | UpdateItem → 更新後レコードを返す |

### `services/storage.py`
S3 との通信および Presigned URL 生成を担当する。

| 関数 | 説明 |
|------|------|
| `generate_document_id()` | UUID hex を生成 |
| `build_document_key(...)` | S3 キーを組み立て |
| `create_presigned_upload_url(s3_key, content_type)` | PUT 用 Presigned URL（デフォルト 15分） |
| `create_presigned_download_url(s3_key, file_name)` | GET 用 Presigned URL（デフォルト 5分、インライン表示） |
| `head_document(s3_key)` | S3 オブジェクトの存在・ヘッダー確認 |

### `services/http.py`
Lambda レスポンス形式のユーティリティ。

- `json_response(status_code, body)` — 成功レスポンス
- `error_response(status_code, message, code=...)` — `{"error": {"code": ..., "message": ...}}` 形式
- `parse_json_body(event)` — Base64 デコード対応のボディパーサー

---

## バリデーションルール (`POST /uploads`)

| 項目 | ルール |
|------|------|
| ファイル名 | `.pdf` 拡張子必須 |
| content_type | `application/pdf` 必須 |
| file_size | 1 byte 以上、`MAX_PDF_SIZE_BYTES` 以下（デフォルト 25MB） |

---

## 環境変数

| 変数名 | デフォルト | 説明 |
|--------|-----------|------|
| `DOCUMENTS_BUCKET_NAME` | 必須 | S3 バケット名 |
| `DOCUMENTS_TABLE_NAME` | 必須 | DynamoDB テーブル名 |
| `MAX_PDF_SIZE_BYTES` | `26214400` (25MB) | 最大アップロードサイズ |
| `UPLOAD_URL_EXPIRES_SECONDS` | `900` (15分) | Upload Presigned URL 有効期限 |
| `DOWNLOAD_URL_EXPIRES_SECONDS` | `300` (5分) | Download Presigned URL 有効期限 |

---

## エラーコード一覧

| コード | HTTP | 説明 |
|--------|------|------|
| `unauthorized` | 401 | JWT 認証失敗 |
| `invalid_json` | 400 | リクエストボディの JSON 解析失敗 |
| `invalid_file` | 400 | ファイル検証失敗（PDF でない、サイズ超過） |
| `missing_document_id` | 400 | document_id パラメータ不足 |
| `not_found` | 404 | ドキュメントが存在しない |
| `upload_not_found` | 409 | S3 にまだアップロードされていない |
| `invalid_content_type` | 400 | ContentType が application/pdf でない |
| `document_not_ready` | 409 | ドキュメントが ready 状態でない |
| `upload_create_failed` | 500 | DynamoDB 書き込み失敗 |
| `complete_failed` | 500 | 完了時 DynamoDB 更新失敗 |

---

## セキュリティ

- **JWT 認証**: 全エンドポイントで Cognito JWT Authorizer を使用
- **オーナー分離**: DynamoDB クエリは `owner_sub` でフィルタするため、他ユーザーのデータには一切アクセスできない
- **Presigned URL**: 時間制限付きの一時的な S3 アクセス権限のみ付与
- **CORS 制限**: CloudFront の配信 URL のみ許可
