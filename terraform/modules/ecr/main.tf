locals {
  # Only create ECR repos for production-critical components
  essential_repos = [
    "mlflow",      # Model registry and tracking
    "feature-store" # Feature serving
  ]
}

resource "aws_ecr_repository" "essential" {
  for_each = toset(local.essential_repos)
  
  name                 = "mlops/${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = var.environment != "prod" # Allow deletion in non-prod
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  encryption_configuration {
    encryption_type = "AES256"
  }
  
  tags = {
    Name        = "mlops/${each.key}"
    Environment = var.environment
  }
}

# Strict lifecycle policy to stay within free tier (500MB)
resource "aws_ecr_lifecycle_policy" "essential" {
  for_each = aws_ecr_repository.essential

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only latest release tag"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["release-"]
          countType     = "imageCountMoreThan"
          countNumber   = 1
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep only 2 latest untagged images"
        selection = {
          tagStatus   = "untagged"
          countType   = "imageCountMoreThan"
          countNumber = 2
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 3
        description  = "Remove images older than 7 days"
        selection = {
          tagStatus   = "any"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Output the repository URLs
output "repository_urls" {
  value = {
    for name, repo in aws_ecr_repository.essential : name => repo.repository_url
  }
}

# Output instructions for using Docker Hub/GHCR for development
output "development_instructions" {
  value = <<EOF
Development Image Repositories:
- Use Docker Hub for development images:
  * kafka: confluentinc/cp-kafka:latest
  * schema-registry: confluentinc/cp-schema-registry:latest
  * spark: apache/spark:latest
  * airflow: apache/airflow:latest
  * rayserve: rayproject/ray:latest
  * data-validation: apache/spark:latest

- Or use GitHub Container Registry (ghcr.io) for custom development images
  Example: ghcr.io/${var.github_org}/mlops-[component]:[tag]

Production deployments should use ECR repositories:
${join("\n", [for repo in aws_ecr_repository.essential : "- ${repo.repository_url}"])}
EOF
} 