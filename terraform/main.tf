terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
  required_version = ">= 1.0"
  
  # S3 backend configuration - uncomment and configure for production use
  /*
  backend "s3" {
    bucket = "mlops-terraform-state"
    key    = "mlops-platform/terraform.tfstate"
    region = "us-west-2"
  }
  */
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "MLOps-Platform"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# EKS cluster
module "eks" {
  source          = "./modules/eks"
  cluster_name    = var.cluster_name
  cluster_version = "1.28"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
  environment     = var.environment
  
  # Node groups configuration
  node_groups = {
    general = {
      instance_types = ["m5.xlarge"]
      min_size       = 2
      max_size       = 5
      desired_size   = 3
    }
    
    compute = {
      instance_types = ["c5.2xlarge"]
      min_size       = 1
      max_size       = 10
      desired_size   = 2
      taints = [
        {
          key    = "workload"
          value  = "compute"
          effect = "NO_SCHEDULE"
        }
      ]
    }
    
    storage = {
      instance_types = ["r5.xlarge"]
      min_size       = 1
      max_size       = 5
      desired_size   = 2
      taints = [
        {
          key    = "workload"
          value  = "storage"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }
}

# VPC for the EKS cluster
module "vpc" {
  source         = "./modules/vpc"
  vpc_name       = "${var.cluster_name}-vpc"
  vpc_cidr       = "10.0.0.0/16"
  azs            = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  environment    = var.environment
}

# ECR repositories for container images
module "ecr" {
  source      = "./modules/ecr"
  repositories = [
    "mlops/kafka",
    "mlops/schema-registry",
    "mlops/spark-driver",
    "mlops/spark-executor",
    "mlops/mlflow",
    "mlops/airflow",
    "mlops/rayserve",
    "mlops/data-validation",
    "mlops/feature-store"
  ]
}

# S3 buckets for artifact storage
module "s3_storage" {
  source        = "./modules/s3"
  bucket_prefix = "mlops-artifacts"
  environment   = var.environment
}

# Create a policy for EKS nodes to access S3
resource "aws_iam_role_policy_attachment" "eks_worker_s3_access" {
  policy_arn = module.s3_storage.bucket_access_policy_arn
  role       = module.eks.worker_iam_role_name
}

# PostgreSQL database
resource "aws_db_subnet_group" "postgres" {
  name       = "postgres-${var.environment}"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name = "PostgreSQL subnet group"
  }
}

resource "aws_security_group" "postgres" {
  name        = "postgres-${var.environment}"
  description = "Allow PostgreSQL inbound traffic"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "PostgreSQL from VPC"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    cidr_blocks     = [module.vpc.vpc_cidr_block]
  }

  egress {
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    cidr_blocks     = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "postgres" {
  identifier             = "mlops-postgres-${var.environment}"
  allocated_storage      = 20
  storage_type           = "gp2"
  engine                 = "postgres"
  engine_version         = "13.17"
  instance_class         = var.db_instance_class
  db_name                = "mlops"
  username               = "postgres"
  password               = var.postgres_password
  parameter_group_name   = "default.postgres13"
  skip_final_snapshot    = true
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  backup_retention_period = 7
  deletion_protection     = var.environment == "prod" ? true : false
}

# Redis for feature store and caching - Using a simpler configuration
resource "aws_elasticache_subnet_group" "redis" {
  name       = "redis-${var.environment}"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name        = "redis-${var.environment}"
  description = "Allow Redis inbound traffic"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Redis from VPC"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    cidr_blocks     = [module.vpc.vpc_cidr_block]
  }

  egress {
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    cidr_blocks     = ["0.0.0.0/0"]
  }
}

# Simplified Redis configuration to avoid provider bug
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "mlops-redis-cache-${var.environment}"
  engine               = "redis"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis6.x"
  engine_version       = "6.x"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]
} 