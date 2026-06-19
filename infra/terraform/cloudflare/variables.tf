variable "cloudflare_api_token" {
  description = "Token with Zone:Read + Zone:Edit + Account:Read on salareen.com."
  type        = string
  sensitive   = true
}

variable "account_id" {
  description = "Cloudflare account ID (under Account Home -> right sidebar)."
  type        = string
}

variable "domain" {
  description = "The zone apex."
  type        = string
  default     = "salareen.com"
}

variable "aws_alb_hostname" {
  description = "AWS Application Load Balancer hostname (output of the AWS Terraform module after the EKS bootstrap installs aws-load-balancer-controller and the Ingress)."
  type        = string
  default     = "REPLACE-AFTER-AWS-APPLY"
}

variable "proxied" {
  description = "Set true once the AWS origin is up - flips on Cloudflare CDN+WAF+DDoS for the API+app records."
  type        = bool
  default     = false
}
