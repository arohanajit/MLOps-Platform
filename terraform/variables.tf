variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "cluster_name" {
  description = "Name for the EKS cluster"
  type        = string
  default     = "mlops-platform"
}

variable "domain_name" {
  description = "Domain name for the platform"
  type        = string
  default     = "mlops.example.com"
}

variable "db_instance_class" {
  description = "Database instance type"
  type        = string
  default     = "db.t3.medium"
}

variable "elasticsearch_instance_type" {
  description = "Elasticsearch instance type"
  type        = string
  default     = "t3.medium.elasticsearch"
}

variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "kafka_instance_type" {
  description = "MSK broker instance type"
  type        = string
  default     = "kafka.m5.large"
}

variable "postgres_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true
  default     = "mlops-Password123!"  # Just a default, should be overridden in tfvars
} 