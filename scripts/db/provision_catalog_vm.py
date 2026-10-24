#!/usr/bin/env python3
"""Create the catalog database VM on Vultr. DRY RUN unless --apply.

The dry run prints the exact API request (secrets redacted) and the monthly cost computed from
Vultr's CURRENT plan prices, and creates nothing. --apply POSTs it once; it refuses to run if a
VM with the same label already exists, so running it twice never creates a second server.

Called by provision_catalog_vm.sh (which just forwards its arguments).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://api.vultr.com/v2"
BACKUP_PCT = 0.20  # Vultr automatic backups cost 20% of the plan price


def call(method: str, path: str, key: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Vultr API {method} {path} failed: {exc.code} {exc.read().decode()[:300]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually create the VM (default: dry run)")
    ap.add_argument("--plan", default="vc2-4c-8gb", help="vc2-4c-8gb (default) or vc2-6c-16gb for >3M courses")
    ap.add_argument("--region", default="sjc", help="must match the cluster region (sjc)")
    ap.add_argument("--label", default="salareen-catalog-db")
    ap.add_argument("--vpc-id", default="", help="the VKE network id (default: discovered, must be exactly one)")
    ap.add_argument("--ssh-key-id", default="", help="Vultr SSH key id (default: discovered if exactly one)")
    ap.add_argument("--admin-cidr", required=True, help="your public IP as x.x.x.x/32 (SSH + psql allowed)")
    ap.add_argument("--no-backups", action="store_true", help="skip Vultr whole-VM backups (+20%% of plan)")
    ap.add_argument("--wal-archive", action="store_true", help="archive WAL to object storage (PITR)")
    args = ap.parse_args()

    key = os.environ.get("VULTR_API_KEY", "")
    if not key:
        print("set VULTR_API_KEY (read-only calls are made even in a dry run)", file=sys.stderr)
        return 2

    plans = {p["id"]: p for p in call("GET", f"/plans?type=vc2&per_page=100", key)["plans"]}
    if args.plan not in plans or args.region not in plans[args.plan].get("locations", []):
        print(f"plan {args.plan} is not offered in {args.region}", file=sys.stderr)
        return 2
    plan = plans[args.plan]
    vpcs = [v for v in call("GET", "/vpcs", key).get("vpcs", []) if v["region"] == args.region]
    vpc = next((v for v in vpcs if v["id"] == args.vpc_id), None) if args.vpc_id else (vpcs[0] if len(vpcs) == 1 else None)
    if vpc is None:
        print("could not pick the VPC: pass --vpc-id. Candidates: " + json.dumps(
            [(v["id"], v["description"], v["v4_subnet"]) for v in vpcs]), file=sys.stderr)
        return 2
    keys = call("GET", "/ssh-keys", key).get("ssh_keys", [])
    ssh = next((k for k in keys if k["id"] == args.ssh_key_id), None) if args.ssh_key_id else (keys[0] if len(keys) == 1 else None)
    if ssh is None:
        print("could not pick an SSH key: pass --ssh-key-id. Candidates: " + json.dumps([(k["id"], k["name"]) for k in keys]), file=sys.stderr)
        return 2
    existing = [i for i in call("GET", "/instances?per_page=500", key).get("instances", []) if i["label"] == args.label]
    vpc_cidr = f'{vpc["v4_subnet"]}/{vpc["v4_subnet_mask"]}'

    render = [sys.executable, str(HERE / "render_cloud_init.py"), "--vpc-cidr", vpc_cidr, "--admin-cidr", args.admin_cidr]
    if args.wal_archive:
        render.append("--wal-archive")
    redacted = subprocess.run(render + ["--redact"], capture_output=True, text=True, check=True).stdout
    body = {
        "region": args.region, "plan": args.plan, "os_id": 2284, "label": args.label, "hostname": args.label,
        "backups": "disabled" if args.no_backups else "enabled", "enable_ipv6": False,
        "sshkey_id": [ssh["id"]], "attach_vpc": [vpc["id"]], "tags": ["salareen", "catalog-db"],
        "activation_email": False, "user_data": "<base64 of the cloud-init below, secrets filled in at --apply>",
    }
    monthly = float(plan["monthly_cost"])
    backups = 0.0 if args.no_backups else round(monthly * BACKUP_PCT, 2)
    print(f"Plan {args.plan}: {plan['vcpu_count']} vCPU, {plan['ram'] // 1024} GB RAM, {plan['disk']} GB NVMe, ${monthly:.2f}/month")
    print(f"Vultr whole-VM backups: ${backups:.2f}/month ({'off' if args.no_backups else '20% of the plan price'})")
    print(f"Estimated monthly total for the server: ${monthly + backups:.2f}")
    print("Not included: dump/WAL storage in the existing object storage subscription (a few GB), bandwidth inside the private network is free.")
    print(f"VPC {vpc['id']} ({vpc['description']}) {vpc_cidr}; SSH key {ssh['name']}; admin CIDR {args.admin_cidr}")
    print("\nRequest that --apply will send:\n  POST " + API + "/instances\n  " + json.dumps(body, indent=2).replace("\n", "\n  "))
    print("\ncloud-init (secrets redacted):\n" + "\n".join("  | " + line for line in redacted.splitlines()[:40]) + "\n  | ... (full file: render_cloud_init.py)")
    if existing:
        print(f"\nA VM labelled {args.label!r} already exists (id {existing[0]['id']}); --apply would refuse to create another.")
    if not args.apply:
        print("\nDRY RUN: nothing was created. Re-run with --apply to create the server (it starts billing immediately).")
        return 0
    if existing:
        print("refusing to create a second server with the same label", file=sys.stderr)
        return 1
    if not (os.environ.get("OBJECT_STORE_ACCESS_KEY") and os.environ.get("OBJECT_STORE_SECRET_KEY")):
        print("export OBJECT_STORE_ACCESS_KEY / OBJECT_STORE_SECRET_KEY first (backups need them)", file=sys.stderr)
        return 2
    user_data = subprocess.run(render, capture_output=True, text=True, check=True).stdout
    body["user_data"] = base64.b64encode(user_data.encode()).decode()
    if len(body["user_data"]) > 60_000:
        print("cloud-init is too large for Vultr user data", file=sys.stderr)
        return 1
    created = call("POST", "/instances", key, body)["instance"]
    print(f"\nCreated instance {created['id']} ({created['label']}). It boots in a few minutes.")
    print("Next: wait for it to become active, read its private IP:")
    print(f"  curl -s -H \"Authorization: Bearer $VULTR_API_KEY\" {API}/instances/{created['id']} | python3 -m json.tool | grep -E 'internal_ip|main_ip|status'")
    print("then: ssh root@<main_ip> 'tail -f /var/log/cloud-init-output.log', run catalog_migrate.py, and set CATALOG_DATABASE_URL.")
    print(f"The database password is in {os.environ.get('CATALOG_DB_PASSWORD_FILE', '~/.config/salareen/catalog-db-password')} (0600).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
