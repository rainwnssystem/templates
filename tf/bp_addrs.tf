# EBS encryption
resource "aws_ebs_encryption_by_default" "default" {
  enabled = true
}


# S3 public access block
resource "aws_s3_account_public_access_block" "default" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


# ECR registry enhanced scanning
resource "aws_ecr_registry_scanning_configuration" "this" {
  scan_type = "ENHANCED"

  rule {
    scan_frequency = "CONTINUOUS_SCAN"
    repository_filter {
      filter      = "*"
      filter_type = "WILDCARD"
    }
  }
}


# Security Hub
resource "aws_securityhub_account" "default" {}


# GuardDuty
resource "aws_guardduty_detector" "default" {
  enable = true
}

locals {
  guardduty_features = [
    "S3_DATA_EVENTS",
    "EKS_AUDIT_LOGS",
    "EBS_MALWARE_PROTECTION",
    "RDS_LOGIN_EVENTS",
    "LAMBDA_NETWORK_LOGS",
    "RUNTIME_MONITORING",
  ]
}

resource "aws_guardduty_detector_feature" "all" {
  for_each    = toset(local.guardduty_features)
  detector_id = aws_guardduty_detector.default.id
  name        = each.value
  status      = "ENABLED"

  dynamic "additional_configuration" {
    for_each = each.value == "RUNTIME_MONITORING" ? [
      { name = "EKS_ADDON_MANAGEMENT", status = "ENABLED" },
      { name = "ECS_FARGATE_AGENT_MANAGEMENT", status = "ENABLED" },
      { name = "EC2_AGENT_MANAGEMENT", status = "ENABLED" },
    ] : []
    content {
      name   = additional_configuration.value.name
      status = additional_configuration.value.status
    }
  }
}


module "guardduty_bucket" {
  source        = "terraform-aws-modules/s3-bucket/aws"
  bucket_prefix = "${var.project_name}-gd"

  force_destroy = true
  versioning = {
    enabled = true
  }

  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        kms_master_key_id = aws_kms_key.guardduty.arn
        sse_algorithm     = "aws:kms"
      }
    }
  }

  lifecycle_rule = [
    {
      id                                     = "garbage_collector"
      enabled                                = true
      abort_incomplete_multipart_upload_days = 1

      noncurrent_version_expiration = {
        days = 14
      }
    }
  ]


  attach_policy = true
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "stmt1"
        Effect    = "Allow"
        Principal = { Service = "guardduty.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${module.guardduty_bucket.s3_bucket_arn}/*"
      },
      {
        Sid       = "stmt2"
        Effect    = "Allow"
        Principal = { Service = "guardduty.amazonaws.com" }
        Action    = "s3:GetBucketLocation"
        Resource  = "${module.guardduty_bucket.s3_bucket_arn}"
      },
      {
        Sid       = "stmt3"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = "${module.guardduty_bucket.s3_bucket_arn}"
      },
      {
        Sid       = "stmt4"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${module.guardduty_bucket.s3_bucket_arn}/*"
      }
    ]
  })
}

resource "aws_kms_key" "guardduty" {
  description             = "KMS key for GuardDuty findings export"
  deletion_window_in_days = 7

  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowAdministration",
      "Effect": "Allow",
      "Principal": { "AWS": "arn:aws:iam::${data.aws_caller_identity.caller.account_id}:root" },
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "AllowAdministration2",
      "Effect": "Allow",
      "Principal": { "AWS": "${data.aws_caller_identity.caller.arn}" },
      "Action": "kms:*",
      "Resource": "*"
    },
    {
      "Sid": "AllowGuardDutyUse",
      "Effect": "Allow",
      "Principal": { "Service": "guardduty.amazonaws.com" },
      "Action": [
        "kms:*"
      ],
      "Resource": "*"
    },
    {
      "Sid": "AllowCloudTrailUse",
      "Effect": "Allow",
      "Principal": { "Service": "cloudtrail.amazonaws.com" },
      "Action": [
        "kms:*"
      ],
      "Resource": "*"
    }
  ]
}
POLICY
}

resource "aws_guardduty_publishing_destination" "findings_export" {
  detector_id     = aws_guardduty_detector.default.id
  destination_arn = module.guardduty_bucket.s3_bucket_arn
  kms_key_arn     = aws_kms_key.guardduty.arn
}

resource "aws_cloudtrail" "default" {
  name                          = "${var.project_name}-cloudtrail"
  s3_bucket_name                = module.guardduty_bucket.s3_bucket_id
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  include_global_service_events = true

  event_selector {
    read_write_type           = "All"
    include_management_events = true
    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::${module.guardduty_bucket.s3_bucket_id}/"]
    }
  }
}