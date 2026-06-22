output "zone_id" {
  value = cloudflare_zone.this.id
}

output "nameservers" {
  description = "Set these at the domain registrar (or use Cloudflare Registrar)."
  value       = cloudflare_zone.this.name_servers
}

output "api_hostname" {
  value = "api.${var.domain}"
}

output "app_hostname" {
  value = "app.${var.domain}"
}
