###############################################################################
# Salareen Cloudflare zone - skeleton
#
# Order of operations (see infra/terraform/RUNBOOK.txt):
#   1. terraform apply with proxied=false  -> DNS-only; verify nameservers
#      at the registrar.
#   2. Bring up AWS (infra/terraform/aws).
#   3. Set aws_alb_hostname = <ALB DNS>; flip proxied=true; apply again.
#
# The WAF + cache rules are intentionally minimal here - they're easier to
# iterate on in the Cloudflare UI first, then commit the final ruleset to
# Terraform once stable.
###############################################################################

resource "cloudflare_zone" "this" {
  account_id = var.account_id
  zone       = var.domain
  plan       = "free"             # upgrade to "pro" / "business" via the UI later
}

# ----- Apex + www marketing -------------------------------------------------
resource "cloudflare_record" "apex" {
  zone_id = cloudflare_zone.this.id
  name    = "@"
  type    = "CNAME"
  value   = var.aws_alb_hostname
  proxied = var.proxied
  ttl     = var.proxied ? 1 : 300   # 1 = "auto" when proxied
}

resource "cloudflare_record" "www" {
  zone_id = cloudflare_zone.this.id
  name    = "www"
  type    = "CNAME"
  value   = var.domain
  proxied = var.proxied
  ttl     = var.proxied ? 1 : 300
}

# ----- API + app subdomains -------------------------------------------------
resource "cloudflare_record" "api" {
  zone_id = cloudflare_zone.this.id
  name    = "api"
  type    = "CNAME"
  value   = var.aws_alb_hostname
  proxied = var.proxied
  ttl     = var.proxied ? 1 : 300
}

resource "cloudflare_record" "app" {
  zone_id = cloudflare_zone.this.id
  name    = "app"
  type    = "CNAME"
  value   = var.aws_alb_hostname
  proxied = var.proxied
  ttl     = var.proxied ? 1 : 300
}

# ----- Email (Cloudflare Email Routing - free) ------------------------------
# Forwards hello@salareen.com -> your inbox until Workspace is set up.
resource "cloudflare_record" "mx_route1" {
  zone_id  = cloudflare_zone.this.id
  name     = "@"
  type     = "MX"
  value    = "route1.mx.cloudflare.net"
  priority = 23
  ttl      = 300
}
resource "cloudflare_record" "mx_route2" {
  zone_id  = cloudflare_zone.this.id
  name     = "@"
  type     = "MX"
  value    = "route2.mx.cloudflare.net"
  priority = 70
  ttl      = 300
}
resource "cloudflare_record" "mx_route3" {
  zone_id  = cloudflare_zone.this.id
  name     = "@"
  type     = "MX"
  value    = "route3.mx.cloudflare.net"
  priority = 70
  ttl      = 300
}
resource "cloudflare_record" "spf" {
  zone_id = cloudflare_zone.this.id
  name    = "@"
  type    = "TXT"
  value   = "v=spf1 include:_spf.mx.cloudflare.net ~all"
  ttl     = 300
}
resource "cloudflare_record" "dmarc" {
  zone_id = cloudflare_zone.this.id
  name    = "_dmarc"
  type    = "TXT"
  # Start in `p=none` for two weeks while you observe; tighten to
  # `p=quarantine` then `p=reject` after.
  value = "v=DMARC1; p=none; rua=mailto:dmarc@${var.domain}; pct=100"
  ttl   = 300
}

# ----- CAA: only Let's Encrypt + ACM may issue certs ------------------------
resource "cloudflare_record" "caa_letsencrypt" {
  zone_id = cloudflare_zone.this.id
  name    = "@"
  type    = "CAA"
  ttl     = 3600
  data {
    flags = 0
    tag   = "issue"
    value = "letsencrypt.org"
  }
}
resource "cloudflare_record" "caa_amazon" {
  zone_id = cloudflare_zone.this.id
  name    = "@"
  type    = "CAA"
  ttl     = 3600
  data {
    flags = 0
    tag   = "issue"
    value = "amazon.com"
  }
}

# ----- Zone-wide settings ---------------------------------------------------
resource "cloudflare_zone_settings_override" "this" {
  zone_id = cloudflare_zone.this.id
  settings {
    ssl                      = "strict"
    always_use_https         = "on"
    automatic_https_rewrites = "on"
    min_tls_version          = "1.2"
    tls_1_3                  = "on"
    opportunistic_encryption = "on"
    brotli                   = "on"
    http3                    = "on"
    zero_rtt                 = "on"
    security_level           = "medium"
    challenge_ttl            = 1800
    websockets               = "on"
    early_hints              = "on"
  }
}
