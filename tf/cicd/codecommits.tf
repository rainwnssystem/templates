locals {
  codecommit_repositories = [
    "product",
    "token",
    "stress",
  ]
}

resource "aws_codecommit_repository" "this" {
  for_each = toset(local.codecommit_repositories)
  repository_name = "${var.project_name}-${each.value}"
}
