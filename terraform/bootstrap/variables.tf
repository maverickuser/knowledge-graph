variable "aws_region" {
  type        = string
  description = "AWS region for the bootstrap resources."
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

variable "state_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name used for Terraform remote state."
}

variable "state_lock_table_name" {
  type        = string
  description = "Optional override for the Terraform state lock table name."
  default     = ""
}
