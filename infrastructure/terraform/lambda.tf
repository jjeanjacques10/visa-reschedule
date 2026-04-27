resource "aws_lambda_function" "webhook" {
  function_name = "${var.project}-${var.environment}-webhook"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "provided.al2023"
  handler       = "bootstrap"
  filename      = "webhook.zip"
  timeout       = 30
  memory_size   = 256

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN = var.telegram_bot_token
      SQS_QUEUE_URL      = var.sqs_queue_url
      DYNAMODB_TABLE     = aws_dynamodb_table.users.name
      AES_SECRET_KEY     = "placeholder"
    }
  }
}

resource "aws_lambda_function" "scheduler" {
  function_name = "${var.project}-${var.environment}-scheduler"
  role          = aws_iam_role.lambda_role.arn
  runtime       = "provided.al2023"
  handler       = "bootstrap"
  filename      = "scheduler.zip"
  timeout       = 60
  memory_size   = 256

  environment {
    variables = {
      SQS_QUEUE_URL  = var.sqs_queue_url
      DYNAMODB_TABLE = aws_dynamodb_table.users.name
      AES_SECRET_KEY = "placeholder"
      TELEGRAM_BOT_TOKEN = "placeholder"
    }
  }
}
