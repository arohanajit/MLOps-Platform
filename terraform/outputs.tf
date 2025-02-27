output "cluster_name" {
  description = "k3s cluster name"
  value       = module.k3s.cluster_name
}

output "kubeconfig_command" {
  description = "Command to get the kubeconfig for k3s cluster"
  value       = module.k3s.kubeconfig_command
}

output "master_public_ip" {
  description = "Public IP of the k3s master node"
  value       = module.k3s.master_public_ip
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