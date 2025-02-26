output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "db_endpoint" {
  description = "PostgreSQL database endpoint"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "postgres_password" {
  description = "PostgreSQL database password"
  value       = var.postgres_password
  sensitive   = true
}

output "artifact_bucket_name" {
  description = "S3 bucket for artifact storage"
  value       = module.s3_storage.bucket_name
}

output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = "${aws_elasticache_cluster.redis.cache_nodes.0.address}:${aws_elasticache_cluster.redis.cache_nodes.0.port}"
  sensitive   = true
} 