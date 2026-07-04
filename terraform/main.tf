terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — configure per environment (bucket + DynamoDB lock table).
  # backend "s3" {
  #   bucket         = "landing-optimizer-tfstate"
  #   key            = "env/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "landing-optimizer-tflock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "landing-optimizer"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ---------------------------------------------------------------------------
# Module wiring (skeleton). Each module lives under ./modules and is filled in
# per the target platform (ECS/Fargate or EKS). Kept as a documented starting
# point rather than fabricated resource definitions.
# ---------------------------------------------------------------------------

# module "network"    { source = "./modules/network"  environment = var.environment }
# module "database"   { source = "./modules/database" ... }   # RDS Postgres (PITR)
# module "clickhouse" { source = "./modules/clickhouse" ... } # managed or self-hosted
# module "redis"      { source = "./modules/redis" ... }      # ElastiCache
# module "compute"    { source = "./modules/compute" ... }    # ECS/Fargate or EKS
# module "cdn"        { source = "./modules/cdn" ... }        # CloudFront for snippet + config
# module "secrets"    { source = "./modules/secrets" ... }    # Secrets Manager / KMS

output "environment" {
  value = var.environment
}
