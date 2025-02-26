output "bucket_name" {
  description = "Name of the artifact S3 bucket"
  value       = aws_s3_bucket.artifact_bucket.id
}

output "bucket_arn" {
  description = "ARN of the artifact S3 bucket"
  value       = aws_s3_bucket.artifact_bucket.arn
}

output "bucket_access_policy_arn" {
  description = "ARN of the IAM policy for bucket access"
  value       = aws_iam_policy.artifact_bucket_access.arn
} 