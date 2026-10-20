terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
  # For team use, move state to S3 with locking:
  # backend "s3" { bucket = "eco-route-tfstate" key = "prod/terraform.tfstate" region = "eu-west-3" use_lockfile = true }
}

provider "aws" {
  region = var.region
  default_tags { tags = { Project = "eco-route", ManagedBy = "terraform" } }
}
