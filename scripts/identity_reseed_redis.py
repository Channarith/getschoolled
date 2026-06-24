#!/usr/bin/env python3
"""Force admin + QA seed accounts into Redis (stdin: kubectl exec -i pod -- python3 -).

Works on identity images back to ~0.3.82 (no identity.persistence module, no
redis PyPI package). Uses a minimal RESP client over TCP when ``redis`` is not
installed. After a successful Redis write, restart identity so every replica
reloads:

  kubectl -n aoep rollout restart deployment/identity
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

for candidate in (
    Path(__file__).resolve().parents[1] / "services" / "identity" / "src",
    Path("/app/services/identity/src"),
):
    if candidate.is_dir() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

REDIS_KEY = "aoep:identity:v1:state"

QA_ALIASES = (
    ("qa1", "qa-learner@salareen.com"),
    ("qa2", "qa-parent@salareen.com"),
    ("qa3", "qa-pro@salareen.com"),
)


def _env_password(key: str, default: str) -> str:
    raw = os.environ.get(key, default)
    val = str(raw or "").strip()
    return val or default


def _redis_url_candidates() -> List[str]:
    seen: set[str] = set()
    urls: List[str] = []
    for raw in (
        os.environ.get("REDIS_URL", ""),
        "redis://redis.aoep.svc.cluster.local:6379/0",
        "redis://redis:6379/0",
        "redis://127.0.0.1:6379/0",
    ):
        url = str(raw or "").strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _parse_redis_url(url: str) -> Tuple[str, int, int, Optional[str]]:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    db = 0
    if parsed.path and parsed.path not in ("", "/"):
        db = int(parsed.path.lstrip("/").split("/")[0] or "0")
    return host, port, db, parsed.password


def _encode_command(*parts: str) -> bytes:
    chunks = [f"*{len(parts)}\r\n".encode("ascii")]
    for part in parts:
        data = part.encode("utf-8")
        chunks.append(f"${len(data)}\r\n".encode("ascii"))
        chunks.append(data + b"\r\n")
    return b"".join(chunks)


def _read_line(sock: socket.socket) -> bytes:
    buf = bytearray()
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("redis connection closed")
        buf.extend(chunk)
        if len(buf) >= 2 and buf[-2:] == b"\r\n":
            return bytes(buf[:-2])


def _read_bulk(sock: socket.socket, length: int) -> bytes:
    data = b""
    while len(data) < length + 2:
        chunk = sock.recv(length + 2 - len(data))
        if not chunk:
            raise ConnectionError("redis connection closed while reading bulk")
        data += chunk
    return data[:length]


def _read_resp(sock: socket.socket):
    prefix = sock.recv(1)
    if not prefix:
        raise ConnectionError("redis connection closed")
    kind = prefix[0:1]
    if kind in (b"+", b"-", b":"):
        line = _read_line(sock)
        text = line.decode("utf-8", errors="replace")
        if kind == b"-":
            raise RuntimeError(text)
        return text
    if kind == b"$":
        line = _read_line(sock)
        length = int(line)
        if length < 0:
            return None
        return _read_bulk(sock, length).decode("utf-8")
    raise RuntimeError(f"unsupported redis reply type: {kind!r}")


class _RawRedis:
    def __init__(self, url: str) -> None:
        host, port, db, password = _parse_redis_url(url)
        self._url = url
        self._sock = socket.create_connection((host, port), timeout=5)
        self._sock.settimeout(5)
        if password:
            self._command("AUTH", password)
        if db:
            self._command("SELECT", str(db))

    def _command(self, *parts: str):
        self._sock.sendall(_encode_command(*parts))
        return _read_resp(self._sock)

    def ping(self) -> bool:
        return self._command("PING") == "PONG"

    def get(self, key: str) -> Optional[str]:
        return self._command("GET", key)

    def set(self, key: str, value: str) -> bool:
        reply = self._command("SET", key, value)
        return reply == "OK"

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


def _redis_client(url: Optional[str] = None):
    urls = [url] if url else _redis_url_candidates()
    last_error: Optional[str] = None
    for candidate in urls:
        if not candidate:
            continue
        try:
            import redis  # type: ignore[import-not-found]

            client = redis.from_url(candidate, decode_responses=True, socket_connect_timeout=5)
            client.ping()
            return client, None
        except ImportError:
            try:
                raw = _RawRedis(candidate)
                raw.ping()
                return raw, None
            except Exception as exc:
                last_error = f"{candidate}: {exc}"
        except Exception as exc:
            last_error = f"{candidate}: {exc}"
    return None, last_error


def _redis_get(client, key: str) -> Optional[str]:
    if hasattr(client, "get") and not isinstance(client, _RawRedis):
        return client.get(key)
    return client.get(key)


def _redis_set(client, key: str, value: str) -> bool:
    if hasattr(client, "set") and not isinstance(client, _RawRedis):
        client.set(key, value)
        return True
    return bool(client.set(key, value))


def _inline_dump_state(store) -> dict:
    accounts = {}
    for aid, acct in store._by_id.items():
        d = acct.model_dump(mode="json")
        d["points_ledger"] = [
            {"delta": e.delta, "reason": e.reason, "ref": e.ref, "ts": e.ts}
            for e in acct.points.entries
        ]
        accounts[aid] = d
    return {
        "accounts": accounts,
        "id_by_email": dict(store._id_by_email),
        "game_stats": getattr(store, "_game_stats", {}),
        "used_grant_nonces": sorted(getattr(store, "_used_grant_nonces", set())),
    }


def _inline_load_state(store, payload: dict) -> None:
    from aoep_shared.rewards import PointsEntry, PointsLedger
    from aoep_shared.schemas import PlanTier, Region
    from identity.store import Account, Enrollment, ProfileShareGrant, StudentProfile

    store._by_id.clear()
    store._id_by_email.clear()
    if hasattr(store, "_game_stats"):
        store._game_stats.clear()
    if hasattr(store, "_used_grant_nonces"):
        store._used_grant_nonces.clear()

    for aid, raw in payload.get("accounts", {}).items():
        row = dict(raw)
        ledger_raw = row.pop("points_ledger", [])
        redemptions = row.pop("redemptions", [])
        enrollments_raw = row.pop("enrollments", {})
        students_raw = row.pop("students", {})
        grants_raw = row.pop("profile_share_grants", {})
        acct = Account(
            id=row["id"],
            email=row["email"],
            display_name=row.get("display_name", ""),
            password_hash=row.get("password_hash", ""),
            tier=PlanTier(row.get("tier", PlanTier.FREE.value)),
            region=Region(row.get("region", Region.US.value)),
            is_admin=bool(row.get("is_admin", False)),
            created_at=float(row.get("created_at", 0)),
            last_login_at=row.get("last_login_at"),
            failed_logins=int(row.get("failed_logins", 0)),
            redemptions=list(redemptions),
        )
        acct.enrollments = {k: Enrollment.model_validate(v) for k, v in enrollments_raw.items()}
        acct.students = {k: StudentProfile.model_validate(v) for k, v in students_raw.items()}
        acct.profile_share_grants = {
            k: ProfileShareGrant.model_validate(v) for k, v in grants_raw.items()
        }
        acct.points = PointsLedger()
        for entry in ledger_raw:
            acct.points.entries.append(PointsEntry(**entry))
        store._by_id[aid] = acct
    store._id_by_email.update(payload.get("id_by_email", {}))
    if hasattr(store, "_game_stats"):
        store._game_stats.update(payload.get("game_stats", {}))
    if hasattr(store, "_used_grant_nonces"):
        store._used_grant_nonces.update(payload.get("used_grant_nonces", []))


def _load_store(store) -> Tuple[bool, Optional[str]]:
    if not os.environ.get("REDIS_URL", "").strip():
        return False, None
    try:
        from identity.persistence import load_from_redis

        return load_from_redis(store), None
    except ImportError:
        client, err = _redis_client()
        if client is None:
            return False, err
        try:
            raw = _redis_get(client, REDIS_KEY)
            if not raw:
                return False, None
            _inline_load_state(store, json.loads(raw))
            return True, None
        except Exception as exc:
            return False, str(exc)
        finally:
            if isinstance(client, _RawRedis):
                client.close()


def _save_store(store, *, attempts: int = 5) -> Tuple[bool, Optional[str]]:
    if not os.environ.get("REDIS_URL", "").strip():
        return True, None
    try:
        from identity.persistence import save_to_redis_with_retry

        return save_to_redis_with_retry(store, attempts=attempts), None
    except ImportError:
        last_error: Optional[str] = None
        payload = json.dumps(_inline_dump_state(store))
        for attempt in range(1, attempts + 1):
            client, err = _redis_client()
            if client is None:
                last_error = err or "no redis client"
            else:
                try:
                    if _redis_set(client, REDIS_KEY, payload):
                        return True, None
                    last_error = "redis SET did not return OK"
                except Exception as exc:
                    last_error = str(exc)
                finally:
                    if isinstance(client, _RawRedis):
                        client.close()
            if attempt < attempts:
                time.sleep(0.4)
        return False, last_error


def _force_passwords(store, emails: list[str], password: str) -> None:
    from aoep_shared.auth import hash_password

    h = hash_password(password)
    for email in emails:
        acct = store.by_email(email)
        if acct is not None:
            acct.password_hash = h


def _register_qa_aliases(store) -> None:
    """Ensure qa1/qa2/qa3 map to the QA personas (old images lack seed_account)."""
    for alias, email in QA_ALIASES:
        acct = store.by_email(email)
        if acct is not None:
            store._id_by_email[alias.strip().lower()] = acct.id


def _seed_account_compat(store, email: str, password: str, **kwargs) -> None:
    try:
        store.seed_account(email, password, **kwargs, force_password=True)
    except TypeError:
        store.seed_account(email, password, **{k: v for k, v in kwargs.items() if k != "force_password"})
        aliases = [email]
        u = kwargs.get("username")
        if u:
            aliases.append(u)
        _force_passwords(store, aliases, password)


def _bootstrap(store) -> dict:
    admin_email = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@salareen.com")
    admin_pw = _env_password("DEFAULT_ADMIN_PASSWORD", "88888888")
    admin_user = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
    qa_pw = _env_password("QA_ACCOUNTS_PASSWORD", "QaTest123")

    try:
        from identity.bootstrap import bootstrap_accounts

        stats = bootstrap_accounts(store)
        _register_qa_aliases(store)
        return stats
    except ImportError:
        pass

    stats: dict = {"admin": False, "qa_count": 0}
    if os.environ.get("SEED_DEFAULT_ADMIN", "1").lower() in ("1", "true", "yes"):
        if hasattr(store, "seed_admin"):
            store.seed_admin(admin_email, admin_pw, username=admin_user)
        elif hasattr(store, "seed_account"):
            _seed_account_compat(
                store, admin_email, admin_pw,
                display_name="Administrator", username=admin_user, is_admin=True,
            )
        else:
            if store.by_email(admin_email) is None:
                store.create(admin_email, admin_pw, display_name="Administrator")
            acct = store.by_email(admin_email)
            if acct is not None:
                acct.is_admin = True
            _force_passwords(store, [admin_email, admin_user], admin_pw)
        stats["admin"] = True

    if os.environ.get("SEED_QA_ACCOUNTS", "1").lower() in ("1", "true", "yes"):
        try:
            from identity.qa_seed import seed_qa_accounts

            seeded = seed_qa_accounts(store, qa_pw)
            stats["qa_count"] = len(seeded)
        except ImportError:
            from aoep_shared.schemas import PlanTier

            qa_rows = (
                ("qa-learner@salareen.com", PlanTier.FREE, "QA Learner"),
                ("qa-parent@salareen.com", PlanTier.FREE, "QA Parent"),
                ("qa-pro@salareen.com", PlanTier.PRO, "QA Pro"),
            )
            for email, tier, display_name in qa_rows:
                acct = store.by_email(email)
                if acct is None:
                    acct = store.create(email, qa_pw, display_name=display_name, tier=tier)
                else:
                    acct.tier = tier
                    acct.display_name = display_name or acct.display_name
            _force_passwords(store, [email for email, _, _ in qa_rows], qa_pw)
            stats["qa_count"] = len(qa_rows)

    _register_qa_aliases(store)
    return stats


def main() -> int:
    from identity.store import AccountStore

    store = AccountStore()
    loaded, load_error = _load_store(store)
    stats = _bootstrap(store)
    persisted, persist_error = _save_store(store)
    qa_pw = _env_password("QA_ACCOUNTS_PASSWORD", "QaTest123")
    admin_pw = _env_password("DEFAULT_ADMIN_PASSWORD", "88888888")
    checks = {
        "admin@salareen.com": store.authenticate("admin@salareen.com", admin_pw) is not None,
        "qa-pro@salareen.com": store.authenticate("qa-pro@salareen.com", qa_pw) is not None,
        "qa3": store.authenticate("qa3", qa_pw) is not None,
    }
    out = {
        "loaded_from_redis": loaded,
        "stats": stats,
        "persisted": persisted,
        "accounts": len(store._by_id),
        "login_ok": checks,
        "next_step": "kubectl -n aoep rollout restart deployment/identity",
    }
    if load_error:
        out["load_error"] = load_error
    if persist_error:
        out["persist_error"] = persist_error
    print(out)
    redis_required = bool(os.environ.get("REDIS_URL", "").strip())
    ok = all(checks.values()) and (persisted or not redis_required)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
