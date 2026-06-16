output "dynamodb_table_name" {
  value = aws_dynamodb_table.graph.name
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.graph.arn
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "github_oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}
