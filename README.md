# Cognito Auth Static Site on AWS

Terraform で以下を構築する最小構成です。

- Amazon Cognito User Pool
- Cognito Hosted UI 用の User Pool Client / Domain
- 非公開 S3 バケット
- CloudFront Distribution + Origin Access Control
- Cognito ログインを使う静的フロント
- PDF アップロード用の S3 / DynamoDB / API Gateway / Lambda

## 構成

- CloudFront 経由で静的フロントを配信します
- フロントは未ログイン時に Cognito Hosted UI へリダイレクトします
- ログイン後は `id_token` を保持してホーム画面を表示します

注意:

- この構成では「CloudFront 自体が Cognito でゲートされる」わけではありません
- 配信される静的アセットは CloudFront から取得可能です
- 画面の利用制限は SPA 側で行います
- 将来、本当に配信レイヤ自体を認証保護したいなら `ALB + authenticate-cognito` か `Lambda@Edge/CloudFront Functions` を検討してください

## ディレクトリ

- `infra/`: Terraform
- `api/`: PDF アップロード API 用 Lambda コード
- `site/`: 配信する静的フロント

## 使い方

1. Terraform 用の変数を作成します

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
```

2. `infra/terraform.tfvars` を編集します

3. デプロイします

```bash
cd infra
terraform init
terraform apply
```

4. `terraform output` に出る CloudFront ドメインへアクセスします
5. その値を使って `site/config.js` を生成し、S3 バケットへ配信ファイルを配置します

```bash
./scripts/render_site_config.sh \
  "$(cd infra && terraform output -raw aws_region)" \
  "$(cd infra && terraform output -raw cognito_hosted_ui_domain)" \
  "$(cd infra && terraform output -raw cognito_user_pool_client_id)" \
  "$(cd infra && terraform output -raw cloudfront_domain_name)" \
  "$(cd infra && terraform output -raw documents_api_base_url)" \
  > site/config.js
```

次に `site/` を S3 へアップロードします

```bash
aws s3 sync site/ "s3://$(cd infra && terraform output -raw site_bucket_name)" --delete
```

初回は `terraform apply` 後に `site/config.js` を埋めてから、`site/` 配下を S3 にアップロードしてください

## 主要な変数

- `project_name`: リソース名プレフィックス
- `aws_region`: デプロイ先リージョン
- `cognito_domain_prefix`: Cognito Hosted UI ドメインのプレフィックス
- `documents_max_upload_bytes`: アップロードできる PDF の最大サイズ
- `upload_url_expires_seconds`: S3 へのアップロード URL 有効期限
- `download_url_expires_seconds`: PDF 表示用 URL 有効期限

## PDF アップロードの流れ

1. ログイン後、静的フロントが Cognito の `access_token` を使って `POST /uploads` を呼びます
2. API は presigned `PUT` URL を返し、ブラウザが PDF を S3 へ直接アップロードします
3. フロントは `POST /documents/{id}/complete` を呼び、DynamoDB 上の状態を `ready` に更新します
4. `GET /documents` で一覧取得、`GET /documents/{id}/download-url` で一時 URL を発行して PDF を開きます

## API 実装メモ

- `api/` 配下の Python コードは `uv` 前提です
- Lambda は Terraform の `archive_file` で `api/src` を zip 化してデプロイします
- API Gateway 側で Cognito JWT authorizer を使うため、Lambda 側で署名検証コードは持っていません
