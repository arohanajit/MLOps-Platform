variable "cluster_name" {
  description = "Name of the k3s cluster"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the k3s cluster will be created"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID where the k3s instances will be created"
  type        = string
}

variable "key_name" {
  description = "Name of the SSH key pair to use for the instances"
  type        = string
}

variable "worker_count" {
  description = "Number of worker nodes to create"
  type        = number
  default     = 2
} 