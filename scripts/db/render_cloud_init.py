#!/usr/bin/env python3
"""Render scripts/db/catalog-db.cloud-init.yaml: fill @TOKENS@ and embed the helper scripts.

Used by provision_catalog_vm.sh. Secrets come from the environment / a 0600 password file, never
from git. With --redact the output shows <redacted> instead of secrets (safe to print).
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import stat
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "catalog-db.cloud-init.yaml"
EMBED_RE = re.compile(r"^(?P<indent>\s*)@EMBED:(?P<name>[A-Za-z0-9_.-]+)@\s*$")


def load_or_create_password(path: Path) -> str:
    if path.is_file():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(32).replace("-", "x").replace("_", "y")  # alnum only: safe in shell/SQL/YAML
    path.write_text(password + "\n")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return password


def render(values: dict[str, str]) -> str:
    out: list[str] = []
    for line in TEMPLATE.read_text().splitlines():
        match = EMBED_RE.match(line)
        if match:
            body = (HERE / match.group("name")).read_text().rstrip("\n").splitlines()
            out.extend((match.group("indent") + b) if b.strip() else "" for b in body)
            continue
        out.append(line)
    text = "\n".join(out) + "\n"
    for key, value in values.items():
        text = text.replace(f"@{key}@", value)
    leftover = sorted(set(re.findall(r"@[A-Z_]+@", text)))
    if leftover:
        raise SystemExit(f"unreplaced tokens in cloud-init: {leftover}")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vpc-cidr", required=True, help="private network allowed to connect, e.g. 10.12.96.0/20")
    ap.add_argument("--admin-cidr", required=True, help="your public IP/32 allowed to SSH (and psql)")
    ap.add_argument("--object-endpoint", default="https://sjc1.vultrobjects.com")
    ap.add_argument("--object-bucket", default="salareen-prod")
    ap.add_argument("--wal-archive", action="store_true", help="also archive WAL to object storage (point in time recovery)")
    ap.add_argument("--password-file", default=str(Path.home() / ".config" / "salareen" / "catalog-db-password"))
    ap.add_argument("--redact", action="store_true")
    args = ap.parse_args()

    access = os.environ.get("OBJECT_STORE_ACCESS_KEY", "")
    secret = os.environ.get("OBJECT_STORE_SECRET_KEY", "")
    if not (access and secret) and not args.redact:
        print("set OBJECT_STORE_ACCESS_KEY / OBJECT_STORE_SECRET_KEY (backups need them)", file=sys.stderr)
        return 2
    password = "<redacted>" if args.redact else load_or_create_password(Path(args.password_file))
    values = {
        "VPC_CIDR": args.vpc_cidr,
        "ADMIN_CIDR": args.admin_cidr,
        "OBJECT_ENDPOINT": args.object_endpoint,
        "OBJECT_BUCKET": args.object_bucket,
        "WAL_ARCHIVE": "1" if args.wal_archive else "0",
        "PG_PASSWORD": "<redacted>" if args.redact else password,
        "OBJECT_ACCESS_KEY": "<redacted>" if args.redact else access,
        "OBJECT_SECRET_KEY": "<redacted>" if args.redact else secret,
    }
    sys.stdout.write(render(values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
