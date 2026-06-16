resource "aws_dynamodb_table" "graph" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "artifact_id"
  range_key    = "version"

  attribute {
    name = "artifact_id"
    type = "S"
  }

  attribute {
    name = "version"
    type = "S"
  }

  attribute {
    name = "artifact_type"
    type = "S"
  }

  attribute {
    name = "graph_version"
    type = "S"
  }

  attribute {
    name = "artifact_sort_key"
    type = "S"
  }

  attribute {
    name = "community_id"
    type = "S"
  }

  attribute {
    name = "assessment_item_id"
    type = "S"
  }

  global_secondary_index {
    name            = "graph-version-index"
    hash_key        = "graph_version"
    range_key       = "artifact_sort_key"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "community-version-index"
    hash_key        = "community_id"
    range_key       = "version"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "assessment-version-index"
    hash_key        = "assessment_item_id"
    range_key       = "version"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = local.tags
}
