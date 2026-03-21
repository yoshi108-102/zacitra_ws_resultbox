variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "Resource name prefix."
  type        = string
}

variable "cognito_domain_prefix" {
  description = "Unique prefix for Cognito Hosted UI domain."
  type        = string
}

variable "tags" {
  description = "Common resource tags."
  type        = map(string)
  default     = {}
}
