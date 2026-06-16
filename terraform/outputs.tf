output "dynamodb_table_name" {
  value = aws_dynamodb_table.graph.name
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.graph.arn
}

output "snapshot_bucket_name" {
  value = aws_s3_bucket.snapshots.bucket
}

output "snapshot_bucket_arn" {
  value = aws_s3_bucket.snapshots.arn
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "github_oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}
