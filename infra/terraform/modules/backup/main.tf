terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

variable "bucket_name" { type = string }
variable "retention_days" { type = number default = 30 }
variable "tags" { type = map(string) default = {} }

resource "aws_s3_bucket" "backup" {
  bucket = var.bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "v" {
  bucket = aws_s3_bucket.backup.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_lifecycle_configuration" "lc" {
  bucket = aws_s3_bucket.backup.id
  rule {
    id     = "expire-old"
    status = "Enabled"
    expiration { days = var.retention_days }
  }
}

output "bucket" { value = aws_s3_bucket.backup.bucket }

