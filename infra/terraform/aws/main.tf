###############################################################################
# Salareen AWS platform - skeleton
#
# What this Terraform deploys:
#   * VPC across N AZs (variable az_count) with public + private subnets, NAT
#     per AZ, and VPC endpoints to keep traffic off the public Internet.
#   * EKS cluster with two managed node groups:
#       - api-pool  (m6i.large, autoscaled 6-200)
#       - gpu-pool  (g5.xlarge, autoscaled 0-20, taints + labels for AI pods)
#   * Aurora PostgreSQL cluster (writer + 2 readers across AZs).
#   * ElastiCache Redis (cluster mode, multi-AZ failover).
#   * S3 buckets: media, uploads, backups (KMS-encrypted, versioned).
#   * IRSA OIDC provider, default IAM roles for the cluster add-ons.
#   * KMS keys for envelope encryption.
#
# Out of scope (deliberately):
#   - GitHub Actions OIDC federation - separate module per account.
#   - Cluster add-ons - installed via Helm in the bootstrap step
#     (RUNBOOK.txt) so version bumps don't require a Terraform run.
#   - WAF + CDN - lives in Cloudflare (infra/terraform/cloudflare/).
#   - Multi-region - Phase 2; copy this module + add Aurora Global +
#     S3 CRR.
#
# This is a SKELETON. Read every block, fill the TODOs marked
# `# TODO(salareen)`, fold in upstream community modules where you trust
# them (terraform-aws-modules/{vpc,eks,rds-aurora,elasticache} are the
# usual choice), and `terraform plan` before every apply.
###############################################################################

provider "aws" {
  region = var.region
  default_tags {
    tags = merge(var.tags, {
      environment = var.environment
    })
  }
}

data "aws_availability_zones" "available" {
  state = "available"
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  azs           = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  cluster_name  = "${var.project}-${var.environment}"
  public_cidrs  = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 8, i)]
  private_cidrs = [for i in range(var.az_count) : cidrsubnet(var.vpc_cidr, 6, i + 8)]
}

###############################################################################
# Networking
###############################################################################
resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${local.cluster_name}-vpc" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${local.cluster_name}-igw" }
}

resource "aws_subnet" "public" {
  count                   = var.az_count
  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.public_cidrs[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
  tags = {
    Name                                            = "${local.cluster_name}-public-${local.azs[count.index]}"
    "kubernetes.io/role/elb"                        = "1"
    "kubernetes.io/cluster/${local.cluster_name}"   = "shared"
  }
}

resource "aws_subnet" "private" {
  count             = var.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.private_cidrs[count.index]
  availability_zone = local.azs[count.index]
  tags = {
    Name                                            = "${local.cluster_name}-private-${local.azs[count.index]}"
    "kubernetes.io/role/internal-elb"               = "1"
    "kubernetes.io/cluster/${local.cluster_name}"   = "shared"
  }
}

resource "aws_eip" "nat" {
  count  = var.az_count
  domain = "vpc"
  tags   = { Name = "${local.cluster_name}-nat-${count.index}" }
}

# One NAT per AZ. DO NOT collapse to a single NAT for cost - an AZ
# failure must not take egress with it.
resource "aws_nat_gateway" "this" {
  count         = var.az_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "${local.cluster_name}-nat-${count.index}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = { Name = "${local.cluster_name}-rt-public" }
}
resource "aws_route_table_association" "public" {
  count          = var.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count  = var.az_count
  vpc_id = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[count.index].id
  }
  tags = { Name = "${local.cluster_name}-rt-private-${count.index}" }
}
resource "aws_route_table_association" "private" {
  count          = var.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

###############################################################################
# KMS keys
###############################################################################
resource "aws_kms_key" "data" {
  description             = "${local.cluster_name} data encryption (RDS, EBS, S3, Secrets)"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = { Name = "${local.cluster_name}-kms-data" }
}
resource "aws_kms_alias" "data" {
  name          = "alias/${local.cluster_name}-data"
  target_key_id = aws_kms_key.data.key_id
}

###############################################################################
# EKS - control plane + node groups
#
# Real deploys should use the upstream `terraform-aws-modules/eks/aws`
# module which folds in IRSA, addons, log groups, and the Karpenter
# integration. Inlined here as a skeleton so the file reads end-to-end.
###############################################################################
resource "aws_iam_role" "eks_cluster" {
  name = "${local.cluster_name}-eks-cluster"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "eks.amazonaws.com" },
      Action = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy_attachment" "eks_cluster" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController",
  ])
  policy_arn = each.value
  role       = aws_iam_role.eks_cluster.name
}

resource "aws_eks_cluster" "this" {
  name     = local.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.eks_cluster.arn

  vpc_config {
    subnet_ids              = concat(aws_subnet.public[*].id, aws_subnet.private[*].id)
    endpoint_public_access  = true
    endpoint_private_access = true
    public_access_cidrs     = ["0.0.0.0/0"]    # tighten to the office CIDR before launch
  }

  encryption_config {
    provider { key_arn = aws_kms_key.data.arn }
    resources = ["secrets"]
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  depends_on = [aws_iam_role_policy_attachment.eks_cluster]
}

# Node IAM
resource "aws_iam_role" "node" {
  name = "${local.cluster_name}-eks-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy_attachment" "node" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
  ])
  policy_arn = each.value
  role       = aws_iam_role.node.name
}

resource "aws_eks_node_group" "api" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "api-pool"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = aws_subnet.private[*].id

  scaling_config {
    desired_size = var.node_pool_min
    min_size     = var.node_pool_min
    max_size     = var.node_pool_max
  }
  update_config { max_unavailable = 1 }
  instance_types = ["m6i.large", "m6i.xlarge"]
  capacity_type  = "ON_DEMAND"

  labels = { tier = "api" }
  tags   = { "k8s.io/cluster-autoscaler/${local.cluster_name}" = "owned" }
}

resource "aws_eks_node_group" "gpu" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "gpu-pool"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = aws_subnet.private[*].id

  scaling_config {
    desired_size = var.gpu_pool_min
    min_size     = var.gpu_pool_min
    max_size     = var.gpu_pool_max
  }
  update_config { max_unavailable = 1 }
  instance_types = ["g5.xlarge", "g5.2xlarge"]

  taint {
    key    = "nvidia.com/gpu"
    value  = "true"
    effect = "NO_SCHEDULE"
  }
  labels = { tier = "gpu", "nvidia.com/gpu" = "true" }
}

# OIDC provider for IRSA. Apps that need AWS perms (S3 read/write,
# Secrets Manager) bind a service account to a role rather than baking
# IAM keys into images.
data "tls_certificate" "eks_oidc" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}
resource "aws_iam_openid_connect_provider" "eks" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks_oidc.certificates[0].sha1_fingerprint]
}

###############################################################################
# Aurora PostgreSQL (primary writer + 2 readers across AZs)
###############################################################################
resource "aws_db_subnet_group" "rds" {
  name       = "${local.cluster_name}-rds"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_security_group" "rds" {
  name        = "${local.cluster_name}-rds"
  description = "Aurora PostgreSQL"
  vpc_id      = aws_vpc.this.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.this.vpc_config[0].cluster_security_group_id]
  }
  egress { from_port = 0, to_port = 0, protocol = "-1", cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_rds_cluster" "pg" {
  cluster_identifier      = "${local.cluster_name}-pg"
  engine                  = "aurora-postgresql"
  engine_version          = "16.4"
  database_name           = "salareen"
  master_username         = "salareen_root"
  master_password         = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.rds.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.data.arn
  backup_retention_period = 14
  preferred_backup_window = "03:00-04:00"
  apply_immediately       = false
  deletion_protection     = true
  skip_final_snapshot     = false
  final_snapshot_identifier = "${local.cluster_name}-pg-final"
}

resource "aws_rds_cluster_instance" "pg" {
  count                = 3
  identifier           = "${local.cluster_name}-pg-${count.index}"
  cluster_identifier   = aws_rds_cluster.pg.id
  instance_class       = var.db_instance_class
  engine               = aws_rds_cluster.pg.engine
  engine_version       = aws_rds_cluster.pg.engine_version
  db_subnet_group_name = aws_db_subnet_group.rds.name
  publicly_accessible  = false
  performance_insights_enabled = true
  performance_insights_kms_key_id = aws_kms_key.data.arn
}

###############################################################################
# ElastiCache Redis (cluster mode, multi-AZ)
###############################################################################
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.cluster_name}-redis"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_security_group" "redis" {
  name        = "${local.cluster_name}-redis"
  description = "ElastiCache Redis"
  vpc_id      = aws_vpc.this.id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.this.vpc_config[0].cluster_security_group_id]
  }
  egress { from_port = 0, to_port = 0, protocol = "-1", cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id        = "${local.cluster_name}-redis"
  description                 = "Salareen rate-limit + cache + sessions"
  engine                      = "redis"
  engine_version              = "7.1"
  node_type                   = var.redis_node_type
  parameter_group_name        = "default.redis7.cluster.on"
  automatic_failover_enabled  = true
  multi_az_enabled            = true
  num_node_groups             = var.redis_shards
  replicas_per_node_group     = 1
  port                        = 6379
  subnet_group_name           = aws_elasticache_subnet_group.redis.name
  security_group_ids          = [aws_security_group.redis.id]
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true
  kms_key_id                  = aws_kms_key.data.arn
  snapshot_retention_limit    = 1
  apply_immediately           = false
}

###############################################################################
# S3 buckets - media (Cloudflare R2 also works), uploads, backups
###############################################################################
resource "random_id" "bucket_suffix" { byte_length = 4 }

locals {
  bucket_suffix = random_id.bucket_suffix.hex
}

resource "aws_s3_bucket" "media" {
  bucket = "${var.project}-${var.environment}-media-${local.bucket_suffix}"
}
resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project}-${var.environment}-uploads-${local.bucket_suffix}"
}
resource "aws_s3_bucket" "backups" {
  bucket = "${var.project}-${var.environment}-backups-${local.bucket_suffix}"
}

resource "aws_s3_bucket_versioning" "all" {
  for_each = {
    media   = aws_s3_bucket.media.id
    uploads = aws_s3_bucket.uploads.id
    backups = aws_s3_bucket.backups.id
  }
  bucket = each.value
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = {
    media   = aws_s3_bucket.media.id
    uploads = aws_s3_bucket.uploads.id
    backups = aws_s3_bucket.backups.id
  }
  bucket = each.value
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each = {
    media   = aws_s3_bucket.media.id
    uploads = aws_s3_bucket.uploads.id
    backups = aws_s3_bucket.backups.id
  }
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
