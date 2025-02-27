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

# Create SSH key pair for EC2 instances
resource "aws_key_pair" "k3s" {
  key_name   = "${var.cluster_name}-key"
  public_key = file(var.ssh_public_key_path)
}

# k3s cluster
module "k3s" {
  source        = "./modules/k3s"
  cluster_name  = var.cluster_name
  environment   = var.environment
  vpc_id        = module.vpc.vpc_id
  subnet_id     = module.vpc.private_subnets[0]
  key_name      = aws_key_pair.k3s.key_name
  worker_count  = 2
}

# VPC for the cluster
module "vpc" {
  source         = "./modules/vpc"
  vpc_name       = "${var.cluster_name}-vpc"
  vpc_cidr       = "10.0.0.0/16"
  azs            = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  environment    = var.environment
}

# ECR repositories for essential components only
module "ecr" {
  source      = "./modules/ecr"
  environment = var.environment
  github_org  = var.github_org
}

# Add development registry credentials secret for Kubernetes
resource "kubernetes_secret" "registry_credentials" {
  metadata {
    name = "registry-credentials"
    namespace = "default"  # Can be created in multiple namespaces if needed
  }

  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        "https://index.docker.io/v1/" = {
          username = var.docker_hub_username
          password = var.docker_hub_password
          auth     = base64encode("${var.docker_hub_username}:${var.docker_hub_password}")
        }
        "ghcr.io" = {
          username = var.github_username
          password = var.github_token
          auth     = base64encode("${var.github_username}:${var.github_token}")
        }
      }
    })
  }

  type = "kubernetes.io/dockerconfigjson"
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
  role       = module.k3s.worker_iam_role_name
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
  max_allocated_storage  = 20  # Disable autoscaling to control costs
  storage_type           = "gp2"
  engine                 = "postgres"
  engine_version         = "13.17"
  instance_class         = "db.t2.micro"  # Free tier eligible
  db_name                = "mlops"
  username               = "postgres"
  password               = var.postgres_password
  parameter_group_name   = "default.postgres13"
  skip_final_snapshot    = true
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  backup_retention_period = 3  # Reduced from 7 to 3 days
  deletion_protection     = false  # Disabled for dev environment
  
  # Performance Insights is not available on t2.micro
  performance_insights_enabled = false
  
  # Maintenance and backup settings
  backup_window           = "03:00-04:00"  # 3-4 AM UTC
  maintenance_window      = "Mon:04:00-Mon:05:00"  # 4-5 AM UTC Monday
  
  # Disable enhanced monitoring to reduce costs
  monitoring_interval     = 0
}

# Redis will be deployed in Kubernetes instead of using ElastiCache 