variable "aws_region" { type = string default = "us-east-1" }
variable "project" { type = string default = "telegram-bot-producer" }
variable "environment" { type = string default = "dev" }
variable "telegram_bot_token" { type = string sensitive = true }
variable "sqs_queue_arn" { type = string }
variable "sqs_queue_url" { type = string }
