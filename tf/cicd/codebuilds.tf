locals {
  codebuild_project_names = [
    "${var.project_name}-product-build"
  ]
  codebuild_image = "aws/codebuild/amazonlinux-x86_64-standard:6.0" # aws/codebuild/amazonlinux-x86_64-standard:6.0 | aws/codebuild/amazonlinux-aarch64-standard:3.0
}

resource "aws_cloudwatch_log_group" "codebuild" {
  count = length(local.codebuild_project_names)

  name = "/aws/codebuild/${local.codebuild_project_names[count.index]}"

  tags = {
    Name = "${local.codebuild_project_names[count.index]}-logs"
  }
}

module "codebuild_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role"
  version = "6.2.1"

  count = length(local.codebuild_project_names)

  name            = "${local.codebuild_project_names[count.index]}-role"
  use_name_prefix = false

  trust_policy_permissions = {
    CodeBuildAssumeRole = {
      actions = ["sts:AssumeRole"]
      principals = [{
        type        = "Service"
        identifiers = ["codebuild.amazonaws.com"]
      }]
    }
  }

  tags = {
    Name = "${local.codebuild_project_names[count.index]}-role"
  }
}

data "aws_iam_policy_document" "codebuild" {
  count = length(local.codebuild_project_names)

  statement {
    sid       = "PullSource"
    actions   = ["codecommit:GitPull"]
    resources = [aws_codecommit_repository.this[local.codecommit_repositories[count.index]].arn]
  }

  statement {
    sid = "WriteBuildLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.codebuild[count.index].arn}:*"]
  }
}

resource "aws_iam_role_policy" "codebuild" {
  count = length(local.codebuild_project_names)

  name   = "${local.codebuild_project_names[count.index]}-policy"
  role   = module.codebuild_role[count.index].name
  policy = data.aws_iam_policy_document.codebuild[count.index].json
}

resource "aws_codebuild_project" "this" {
  count = length(local.codebuild_project_names)

  name         = local.codebuild_project_names[count.index]
  service_role = module.codebuild_role[count.index].arn

  depends_on = [aws_iam_role_policy.codebuild]

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = local.codebuild_image
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = true
    type                        = strcontains(local.codebuild_image, "aarch64") ? "ARM_CONTAINER" : "LINUX_CONTAINER"
  }

  logs_config {
    cloudwatch_logs {
      group_name  = aws_cloudwatch_log_group.codebuild[count.index].name
      stream_name = "${local.codebuild_project_names[count.index]}-build"
      status      = "ENABLED"
    }

    s3_logs {
      status = "DISABLED"
    }
  }

  source {
    git_clone_depth = 1
    location        = aws_codecommit_repository.this[local.codecommit_repositories[count.index]].clone_url_http
    type            = "CODECOMMIT"
  }

  tags = {
    Name = local.codebuild_project_names[count.index]
  }
}
