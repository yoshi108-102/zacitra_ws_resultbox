locals {
  common_tags = merge(
    {
      Project = var.project_name
      Managed = "terraform"
    },
    var.tags
  )

  site_origin_id      = "${var.project_name}-site-origin"
  cloudfront_base_url = "https://${aws_cloudfront_distribution.site.domain_name}"
}

data "archive_file" "documents_api" {
  type        = "zip"
  source_dir  = "${path.module}/../api/src"
  output_path = "${path.module}/build/documents-api.zip"
}

resource "aws_s3_bucket" "site" {
  bucket        = "${var.project_name}-site"
  force_destroy = true

  tags = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket = aws_s3_bucket.site.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "site" {
  bucket = aws_s3_bucket.site.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${var.project_name}-site-oac"
  description                       = "OAC for static site bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_200"

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
    origin_id                = local.site_origin_id
  }

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = local.site_origin_id

    viewer_protocol_policy = "redirect-to-https"
    compress               = true

    forwarded_values {
      query_string = false

      cookies {
        forward = "none"
      }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  tags = local.common_tags
}

data "aws_iam_policy_document" "site_bucket_policy" {
  statement {
    sid    = "AllowCloudFrontServicePrincipalReadOnly"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site_bucket_policy.json
}

resource "aws_s3_bucket" "documents" {
  bucket        = "${var.project_name}-documents"
  force_destroy = true

  tags = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "HEAD"]
    allowed_origins = [local.cloudfront_base_url]
    expose_headers  = ["ETag"]
    max_age_seconds = 300
  }
}

resource "aws_dynamodb_table" "documents" {
  name         = "${var.project_name}-documents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "owner_sub"
  range_key    = "document_id"

  attribute {
    name = "owner_sub"
    type = "S"
  }

  attribute {
    name = "document_id"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  tags = local.common_tags
}

resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-users"

  auto_verified_attributes = ["email"]

  username_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  schema {
    attribute_data_type = "String"
    mutable             = true
    name                = "email"
    required            = true

    string_attribute_constraints {
      min_length = 5
      max_length = 256
    }
  }

  tags = local.common_tags
}

resource "aws_cognito_user_pool_client" "site" {
  name         = "${var.project_name}-site-client"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  supported_identity_providers         = ["COGNITO"]

  callback_urls = ["${local.cloudfront_base_url}/callback.html"]
  logout_urls   = ["${local.cloudfront_base_url}/"]

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  prevent_user_existence_errors = "ENABLED"
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_apigatewayv2_api" "documents" {
  name          = "${var.project_name}-documents-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_headers = ["authorization", "content-type"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_origins = [local.cloudfront_base_url]
    max_age       = 300
  }

  tags = local.common_tags
}

resource "aws_apigatewayv2_stage" "documents_default" {
  api_id      = aws_apigatewayv2_api.documents.id
  name        = "$default"
  auto_deploy = true

  tags = local.common_tags
}

resource "aws_apigatewayv2_authorizer" "documents_jwt" {
  api_id           = aws_apigatewayv2_api.documents.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${var.project_name}-documents-jwt"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.site.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

data "aws_iam_policy_document" "documents_api_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "documents_api" {
  name               = "${var.project_name}-documents-api-role"
  assume_role_policy = data.aws_iam_policy_document.documents_api_assume_role.json

  tags = local.common_tags
}

data "aws_iam_policy_document" "documents_api_permissions" {
  statement {
    sid    = "AllowCloudWatchLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }

  statement {
    sid    = "AllowDocumentsBucketAccess"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.documents.arn}/*"]
  }

  statement {
    sid    = "AllowDocumentsTableAccess"
    effect = "Allow"

    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:UpdateItem",
    ]
    resources = [aws_dynamodb_table.documents.arn]
  }
}

resource "aws_iam_role_policy" "documents_api" {
  name   = "${var.project_name}-documents-api-policy"
  role   = aws_iam_role.documents_api.id
  policy = data.aws_iam_policy_document.documents_api_permissions.json
}

resource "aws_lambda_function" "create_upload" {
  function_name    = "${var.project_name}-create-upload"
  role             = aws_iam_role.documents_api.arn
  runtime          = "python3.12"
  handler          = "handlers.create_upload.handler"
  filename         = data.archive_file.documents_api.output_path
  source_code_hash = data.archive_file.documents_api.output_base64sha256
  timeout          = 15

  environment {
    variables = {
      DOCUMENTS_BUCKET_NAME        = aws_s3_bucket.documents.bucket
      DOCUMENTS_TABLE_NAME         = aws_dynamodb_table.documents.name
      MAX_PDF_SIZE_BYTES           = tostring(var.documents_max_upload_bytes)
      UPLOAD_URL_EXPIRES_SECONDS   = tostring(var.upload_url_expires_seconds)
      DOWNLOAD_URL_EXPIRES_SECONDS = tostring(var.download_url_expires_seconds)
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "complete_upload" {
  function_name    = "${var.project_name}-complete-upload"
  role             = aws_iam_role.documents_api.arn
  runtime          = "python3.12"
  handler          = "handlers.complete_upload.handler"
  filename         = data.archive_file.documents_api.output_path
  source_code_hash = data.archive_file.documents_api.output_base64sha256
  timeout          = 15

  environment {
    variables = {
      DOCUMENTS_BUCKET_NAME        = aws_s3_bucket.documents.bucket
      DOCUMENTS_TABLE_NAME         = aws_dynamodb_table.documents.name
      MAX_PDF_SIZE_BYTES           = tostring(var.documents_max_upload_bytes)
      UPLOAD_URL_EXPIRES_SECONDS   = tostring(var.upload_url_expires_seconds)
      DOWNLOAD_URL_EXPIRES_SECONDS = tostring(var.download_url_expires_seconds)
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "list_documents" {
  function_name    = "${var.project_name}-list-documents"
  role             = aws_iam_role.documents_api.arn
  runtime          = "python3.12"
  handler          = "handlers.list_documents.handler"
  filename         = data.archive_file.documents_api.output_path
  source_code_hash = data.archive_file.documents_api.output_base64sha256
  timeout          = 15

  environment {
    variables = {
      DOCUMENTS_BUCKET_NAME        = aws_s3_bucket.documents.bucket
      DOCUMENTS_TABLE_NAME         = aws_dynamodb_table.documents.name
      MAX_PDF_SIZE_BYTES           = tostring(var.documents_max_upload_bytes)
      UPLOAD_URL_EXPIRES_SECONDS   = tostring(var.upload_url_expires_seconds)
      DOWNLOAD_URL_EXPIRES_SECONDS = tostring(var.download_url_expires_seconds)
    }
  }

  tags = local.common_tags
}

resource "aws_lambda_function" "get_download_url" {
  function_name    = "${var.project_name}-get-download-url"
  role             = aws_iam_role.documents_api.arn
  runtime          = "python3.12"
  handler          = "handlers.get_download_url.handler"
  filename         = data.archive_file.documents_api.output_path
  source_code_hash = data.archive_file.documents_api.output_base64sha256
  timeout          = 15

  environment {
    variables = {
      DOCUMENTS_BUCKET_NAME        = aws_s3_bucket.documents.bucket
      DOCUMENTS_TABLE_NAME         = aws_dynamodb_table.documents.name
      MAX_PDF_SIZE_BYTES           = tostring(var.documents_max_upload_bytes)
      UPLOAD_URL_EXPIRES_SECONDS   = tostring(var.upload_url_expires_seconds)
      DOWNLOAD_URL_EXPIRES_SECONDS = tostring(var.download_url_expires_seconds)
    }
  }

  tags = local.common_tags
}

resource "aws_apigatewayv2_integration" "create_upload" {
  api_id                 = aws_apigatewayv2_api.documents.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.create_upload.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "complete_upload" {
  api_id                 = aws_apigatewayv2_api.documents.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.complete_upload.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "list_documents" {
  api_id                 = aws_apigatewayv2_api.documents.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.list_documents.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "get_download_url" {
  api_id                 = aws_apigatewayv2_api.documents.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.get_download_url.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "create_upload" {
  api_id             = aws_apigatewayv2_api.documents.id
  route_key          = "POST /uploads"
  target             = "integrations/${aws_apigatewayv2_integration.create_upload.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.documents_jwt.id
}

resource "aws_apigatewayv2_route" "complete_upload" {
  api_id             = aws_apigatewayv2_api.documents.id
  route_key          = "POST /documents/{document_id}/complete"
  target             = "integrations/${aws_apigatewayv2_integration.complete_upload.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.documents_jwt.id
}

resource "aws_apigatewayv2_route" "list_documents" {
  api_id             = aws_apigatewayv2_api.documents.id
  route_key          = "GET /documents"
  target             = "integrations/${aws_apigatewayv2_integration.list_documents.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.documents_jwt.id
}

resource "aws_apigatewayv2_route" "get_download_url" {
  api_id             = aws_apigatewayv2_api.documents.id
  route_key          = "GET /documents/{document_id}/download-url"
  target             = "integrations/${aws_apigatewayv2_integration.get_download_url.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.documents_jwt.id
}

resource "aws_lambda_permission" "create_upload" {
  statement_id  = "AllowCreateUploadFromApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.create_upload.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.documents.execution_arn}/*/*"
}

resource "aws_lambda_permission" "complete_upload" {
  statement_id  = "AllowCompleteUploadFromApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.complete_upload.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.documents.execution_arn}/*/*"
}

resource "aws_lambda_permission" "list_documents" {
  statement_id  = "AllowListDocumentsFromApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.list_documents.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.documents.execution_arn}/*/*"
}

resource "aws_lambda_permission" "get_download_url" {
  statement_id  = "AllowGetDownloadUrlFromApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.get_download_url.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.documents.execution_arn}/*/*"
}
