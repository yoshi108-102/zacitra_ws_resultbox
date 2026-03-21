output "aws_region" {
  value       = var.aws_region
  description = "AWS region."
}

output "cloudfront_domain_name" {
  value       = aws_cloudfront_distribution.site.domain_name
  description = "CloudFront distribution domain."
}

output "site_bucket_name" {
  value       = aws_s3_bucket.site.bucket
  description = "S3 bucket for site assets."
}

output "cognito_user_pool_id" {
  value       = aws_cognito_user_pool.main.id
  description = "Cognito User Pool ID."
}

output "cognito_user_pool_client_id" {
  value       = aws_cognito_user_pool_client.site.id
  description = "Cognito app client ID."
}

output "cognito_hosted_ui_domain" {
  value       = "${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
  description = "Cognito Hosted UI domain."
}
