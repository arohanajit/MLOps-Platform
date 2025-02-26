resource "aws_ecr_repository" "this" {
  for_each = toset(var.repositories)
  
  name                 = each.key
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  encryption_configuration {
    encryption_type = "AES256"
  }
  
  tags = {
    Name        = each.key
    Environment = var.environment
  }
}

# Lifecycle policy to keep only the latest 20 images
resource "aws_ecr_lifecycle_policy" "this" {
  for_each = toset(var.repositories)
  
  repository = aws_ecr_repository.this[each.key].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 20 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 20
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
} 