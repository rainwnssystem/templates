locals {
  repositories = [
    "product",
    "token",
    "stress"
  ]

  repository_encryption_type = "KMS"
  create_ecr_kms_key = local.repository_encryption_type == "KMS"
}

resource "aws_kms_key" "ecr" {
  count = local.create_ecr_kms_key ? 1 : 0

  description             = "${var.project_name} ECR SSE-KMS CMK"
  enable_key_rotation     = true
  deletion_window_in_days = 7
  tags                    = { Name = "${var.project_name}-ecr-cmk" }
}

resource "aws_kms_alias" "ecr" {
  count = local.create_ecr_kms_key ? 1 : 0

  name          = "alias/${var.project_name}-ecr"
  target_key_id = aws_kms_key.ecr[0].key_id
}

module "ecr" {
  source  = "terraform-aws-modules/ecr/aws"
  version = "~> 3.0"

  for_each = toset(local.repositories)

  repository_name                 = "${var.project_name}-${each.value}"
  repository_image_tag_mutability = "IMMUTABLE"
  # repository_image_scan_on_push   = true

  repository_encryption_type = local.repository_encryption_type
  repository_kms_key         = local.create_ecr_kms_key ? aws_kms_key.ecr[0].arn : null

  repository_read_write_access_arns = [data.aws_caller_identity.caller.arn]

  repository_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images older than 14 days"
        selection    = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 14 }
        action       = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the last 30 images"
        selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 30 }
        action       = { type = "expire" }
      },
    ]
  })

  tags = { Name = "${var.project_name}-${each.value}" }
}
