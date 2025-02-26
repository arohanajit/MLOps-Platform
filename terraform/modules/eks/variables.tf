variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version to use for the EKS cluster"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the EKS cluster will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for the EKS cluster"
  type        = list(string)
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
}

variable "node_groups" {
  description = "Map of EKS node group configurations"
  type        = map(object({
    instance_types = list(string)
    min_size       = number
    max_size       = number
    desired_size   = number
    taints         = optional(list(object({
      key    = string
      value  = string
      effect = string
    })), [])
  }))
  default = {}
} 