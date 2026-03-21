# Cognito Auth Static Site on AWS

Terraform で以下を構築する最小構成です。

- Amazon Cognito User Pool
- Cognito Hosted UI 用の User Pool Client / Domain
- 非公開 S3 バケット
- CloudFront Distribution + Origin Access Control
- Cognito ログインを使う静的フロント

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
- `callback_urls`: ログイン後のリダイレクト URL
- `logout_urls`: ログアウト後のリダイレクト URL
  - このサンプルでは CloudFront ドメインから自動生成されます

## 次の拡張

- API Gateway + Lambda を追加して `/me` や将来のアップロード API を実装
- private S3 バケットを文献保管にも流用
- presigned URL で HTML / PDF アップロードを追加
