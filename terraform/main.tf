locals {
  table_name           = var.dynamodb_table_name != "" ? var.dynamodb_table_name : "${var.project_name}-${var.environment}"
  snapshot_bucket_name = var.snapshot_bucket_name != "" ? var.snapshot_bucket_name : "${var.project_name}-${var.environment}-snapshots-${data.aws_caller_identity.current.account_id}"

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

data "aws_caller_identity" "current" {}
