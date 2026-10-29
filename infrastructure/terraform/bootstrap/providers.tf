provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project   = "progress-tracker"
      ManagedBy = "Terraform"
      Component = "bootstrap"
    }
  }
}