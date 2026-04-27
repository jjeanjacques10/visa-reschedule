resource "aws_sqs_queue_policy" "producer_send" {
  queue_url = var.sqs_queue_url
  policy    = data.aws_iam_policy_document.sqs_policy.json
}

data "aws_iam_policy_document" "sqs_policy" {
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [var.sqs_queue_arn]
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
  }
}
