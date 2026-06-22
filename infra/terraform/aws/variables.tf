variable "project" {
  description = "Resource name prefix; kebab-case, no AWS reserved words."
  type        = string
  default     = "salareen"
}

variable "environment" {
  description = "prod | stg | dev. Drives sizing + tagging."
  type        = string
  default     = "prod"
}

variable "region" {
  description = "Primary AWS region (Phase 1)."
  type        = string
  default     = "us-east-1"
}

variable "az_count" {
  description = "How many AZs to spread the VPC across. Production = 3."
  type        = number
  default     = 3
}

variable "vpc_cidr" {
  description = "VPC IPv4 CIDR. Carve /22s for private subnets so EKS pods don't run out of IPs."
  type        = string
  default     = "10.0.0.0/16"
}

variable "kubernetes_version" {
  description = "EKS control plane version. Bump quarterly."
  type        = string
  default     = "1.30"
}

variable "node_pool_min" {
  description = "API pool minimum nodes. ALWAYS >= az_count so a node-AZ outage leaves a working majority."
  type        = number
  default     = 6
}

variable "node_pool_max" {
  description = "API pool ceiling. Cluster autoscaler scales between this and node_pool_min."
  type        = number
  default     = 200
}

variable "gpu_pool_min" {
  description = "GPU pool minimum (g5.xlarge). 0 saves money when no GPU traffic; >=2 when serving."
  type        = number
  default     = 0
}

variable "gpu_pool_max" {
  description = "GPU pool ceiling."
  type        = number
  default     = 20
}

variable "db_instance_class" {
  description = "Aurora PostgreSQL writer class. db.r6g.large fine until ~5k tx/s."
  type        = string
  default     = "db.r6g.xlarge"
}

variable "db_password" {
  description = "Aurora master password. In production, source from Secrets Manager (see RUNBOOK)."
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.r6g.large"
}

variable "redis_shards" {
  description = "Cluster-mode shard count. 1 is fine until you hit the per-shard limit (~50k ops/s)."
  type        = number
  default     = 2
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
  default = {
    project   = "salareen"
    managed   = "terraform"
    component = "platform"
  }
}
