resource "aws_dynamodb_table" "users" {
  name         = "visa-rescheduler-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute { name = "id" type = "S" }
  attribute { name = "chat_id" type = "N" }
  attribute { name = "portal_username" type = "S" }

  global_secondary_index {
    name            = "telegram-index"
    hash_key        = "chat_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "email-index"
    hash_key        = "portal_username"
    projection_type = "ALL"
  }
}
