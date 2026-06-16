output "state_bucket_name" {
  value = aws_s3_bucket.terraform_state.bucket
}

output "state_bucket_arn" {
  value = aws_s3_bucket.terraform_state.arn
}

output "state_lock_table_name" {
  value = aws_dynamodb_table.terraform_lock.name
}

output "state_lock_table_arn" {
  value = aws_dynamodb_table.terraform_lock.arn
}
