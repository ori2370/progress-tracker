data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_role" "github_ecr_publish" {
  name        = "progress-tracker-github-ecr-publish"
  description = "Allows Progress Tracker GitHub Actions to publish ECR images."

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Federated = data.aws_iam_openid_connect_provider.github.arn
        }

        Action = "sts:AssumeRoleWithWebIdentity"

        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = var.github_oidc_subject
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "github_ecr_publish" {
  name = "publish-progress-tracker-image"
  role = aws_iam_role.github_ecr_publish.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid      = "AuthenticateToECR"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "PublishApplicationImages"
        Effect = "Allow"

        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]

        Resource = aws_ecr_repository.app.arn
      }
    ]
  })
}



data "aws_caller_identity" "current" {}

resource "aws_iam_role" "github_deploy" {
  name        = "progress-tracker-github-deploy"
  description = "Allows GitHub Actions to deploy through Systems Manager."

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Federated = data.aws_iam_openid_connect_provider.github.arn
        }

        Action = "sts:AssumeRoleWithWebIdentity"

        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = var.github_oidc_subject
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "deploy-progress-tracker"
  role = aws_iam_role.github_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid      = "UseShellCommandDocument"
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = "arn:aws:ssm:us-east-1::document/AWS-RunShellScript"
      },
      {
        Sid      = "TargetProjectRuntimeInstances"
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = "arn:aws:ec2:us-east-1:${data.aws_caller_identity.current.account_id}:instance/*"

        Condition = {
          StringEquals = {
            "ssm:resourceTag/Project"   = "progress-tracker"
            "ssm:resourceTag/Component" = "runtime"
          }
        }
      },
      {
        Sid      = "ReadCommandResult"
        Effect   = "Allow"
        Action   = "ssm:GetCommandInvocation"
        Resource = "*"
      }
    ]
  })
}