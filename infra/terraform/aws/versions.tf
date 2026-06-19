terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Remote state goes in S3 + a DynamoDB lock table created out-of-band
  # (see infra/terraform/RUNBOOK.txt). Override on `terraform init` via
  # -backend-config so the same module deploys to multiple environments.
  backend "s3" {
    bucket         = "salareen-tfstate-PROD"
    key            = "aws/main.tfstate"
    region         = "us-east-1"
    dynamodb_table = "salareen-tfstate-locks"
    encrypt        = true
  }
}
