terraform {
  backend "s3" {
    bucket         = var.tf_state_bucket
    key            = "staging/terraform.tfstate"
    region         = var.aws_region
    dynamodb_table = var.tf_state_lock_table
    encrypt        = true
  }
}


