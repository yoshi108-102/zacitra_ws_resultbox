variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "Resource name prefix."
  type        = string
  default     = "zacitra-auth-dev"
}

variable "cognito_domain_prefix" {
  description = "Unique prefix for Cognito Hosted UI domain."
  type        = string
  default     = "zacitra-auth-dev-login"
}

variable "tags" {
  description = "Common resource tags."
  type        = map(string)
  default     = {}
}

variable "documents_max_upload_bytes" {
  description = "Maximum allowed PDF size in bytes."
  type        = number
  default     = 26214400
}

variable "upload_url_expires_seconds" {
  description = "Expiration time for upload URLs in seconds."
  type        = number
  default     = 900
}

variable "download_url_expires_seconds" {
  description = "Expiration time for download URLs in seconds."
  type        = number
  default     = 300
}
