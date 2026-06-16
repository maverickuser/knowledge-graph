variable "aws_region" {
  type        = string
  description = "AWS region for DynamoDB and IAM resources."
  default     = "ap-south-1"
}

variable "project_name" {
  type        = string
  description = "Project name used in resource naming."
  default     = "knowledge-graph"
}

variable "environment" {
  type        = string
  description = "Deployment environment name."
  default     = "dev"
}

variable "dynamodb_table_name" {
  type        = string
  description = "Optional override for the DynamoDB table name."
  default     = ""
}

variable "snapshot_bucket_name" {
  type        = string
  description = "Optional override for the S3 bucket that stores full graph snapshots."
  default     = ""
}

variable "github_repository" {
  type        = string
  description = "GitHub repository in owner/name format."
}

