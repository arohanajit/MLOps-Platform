resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_s3_bucket" "mlops" {
  bucket = "${var.bucket_prefix}-${var.environment}"

  tags = merge(
    {
      Name        = "${var.bucket_prefix}-${var.environment}"
      Environment = var.environment
    },
    var.tags
  )
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "mlops" {
  bucket = aws_s3_bucket.mlops.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning
resource "aws_s3_bucket_versioning" "mlops" {
  bucket = aws_s3_bucket.mlops.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "mlops" {
  bucket = aws_s3_bucket.mlops.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle rules
resource "aws_s3_bucket_lifecycle_configuration" "mlops" {
  bucket = aws_s3_bucket.mlops.id

  # Rule for ML model artifacts
  rule {
    id     = "model_artifacts"
    status = "Enabled"
    filter {
      prefix = "models/"
    }

    # Move non-current versions to cheaper storage
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }
    # Delete old versions after 60 days (reduced from 90)
    noncurrent_version_expiration {
      noncurrent_days = 60
    }
    # Keep only last 2 versions (reduced from 3)
    noncurrent_version_expiration {
      newer_noncurrent_versions = 2
    }
    # Add size-based transition for large objects
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  # Rule for experiment tracking data
  rule {
    id     = "experiment_data"
    status = "Enabled"
    filter {
      prefix = "mlflow/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    expiration {
      days = 180  # Reduced from 365
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  # Rule for temporary data
  rule {
    id     = "temp_data"
    status = "Enabled"
    filter {
      prefix = "temp/"
    }
    
    expiration {
      days = 3  # Reduced from 7
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  # Rule for logs
  rule {
    id     = "logs"
    status = "Enabled"
    filter {
      prefix = "logs/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    expiration {
      days = 60  # Reduced from 90
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Add bucket metrics for monitoring free tier usage
resource "aws_s3_bucket_metric" "free_tier_monitoring" {
  bucket = aws_s3_bucket.mlops.id
  name   = "EntireBucket"
}

# Bucket policy
resource "aws_s3_bucket_policy" "mlops" {
  bucket = aws_s3_bucket.mlops.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceTLS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.mlops.arn,
          "${aws_s3_bucket.mlops.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

# IAM policy for bucket access
resource "aws_iam_policy" "bucket_access" {
  name        = "mlops-s3-access-${var.environment}"
  description = "Policy for accessing MLOps S3 bucket"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.mlops.arn,
          "${aws_s3_bucket.mlops.arn}/*"
        ]
      }
    ]
  })
} 