variable "repositories" {
  description = "List of ECR repository names to create"
  type        = list(string)
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "github_org" {
  description = "GitHub organization name for container registry references"
  type        = string
  default     = "your-org"  # Replace with your GitHub org name
} 