output "ecr_repository_url" {
  description = "Repository URL used to publish application images."
  value       = aws_ecr_repository.app.repository_url
}

output "github_ecr_publish_role_arn" {
  description = "IAM role assumed by GitHub Actions when publishing images."
  value       = aws_iam_role.github_ecr_publish.arn
}