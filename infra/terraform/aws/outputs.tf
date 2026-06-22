output "cluster_name" {
  description = "EKS cluster name; pass to `aws eks update-kubeconfig`."
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "EKS API endpoint."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_ca" {
  description = "EKS cluster CA, base64-encoded."
  value       = aws_eks_cluster.this.certificate_authority[0].data
  sensitive   = true
}

output "oidc_provider_arn" {
  description = "Use to bind k8s ServiceAccounts to AWS IAM roles via IRSA."
  value       = aws_iam_openid_connect_provider.eks.arn
}

output "vpc_id" {
  value = aws_vpc.this.id
}

output "private_subnets" {
  value = aws_subnet.private[*].id
}

output "rds_writer_endpoint" {
  description = "Aurora writer endpoint; goes into DATABASE_URL."
  value       = aws_rds_cluster.pg.endpoint
}

output "rds_reader_endpoint" {
  description = "Aurora reader endpoint; route read-heavy services here."
  value       = aws_rds_cluster.pg.reader_endpoint
}

output "redis_primary_endpoint" {
  description = "ElastiCache configuration endpoint for cluster-mode clients."
  value       = aws_elasticache_replication_group.redis.configuration_endpoint_address
}

output "media_bucket" {
  value = aws_s3_bucket.media.bucket
}

output "uploads_bucket" {
  value = aws_s3_bucket.uploads.bucket
}

output "backups_bucket" {
  value = aws_s3_bucket.backups.bucket
}
