resource "aws_iam_role" "lambda_role" {
  name = "${var.project}-${var.environment}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project}-${var.environment}-lambda-policy"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = "*" },
      { Effect = "Allow", Action = ["dynamodb:PutItem", "dynamodb:Query", "dynamodb:Scan", "dynamodb:DeleteItem"], Resource = [aws_dynamodb_table.users.arn, "${aws_dynamodb_table.users.arn}/index/*"] },
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = var.sqs_queue_arn }
    ]
  })
}
