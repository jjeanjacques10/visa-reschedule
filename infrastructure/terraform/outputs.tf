output "webhook_url" { value = aws_apigatewayv2_stage.webhook_stage.invoke_url }
output "users_table_name" { value = aws_dynamodb_table.users.name }
output "scheduler_rule_arn" { value = aws_cloudwatch_event_rule.dispatch_active_users.arn }
