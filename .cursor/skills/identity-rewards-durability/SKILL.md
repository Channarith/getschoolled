---
name: identity-rewards-durability
description: How accounts, auth, student profiles, points/rewards, admin access, and feature flags work — and the Redis durability model behind them. Use for signup/login, membership/VIP tiers, the points ledger + prize catalog, the seeded admin account, the ADMIN_SECRET feature-flags gate, or when "points/accounts/onboarding survey reset after a redeploy" or an admin 404/401. The identity service is a system of record backed by a Redis snapshot; treating Redis as a throwaway cache loses user data.
---

# Identity, rewards & durability

## Where things live
- Service: `services/identity` (pkg `identity`, port 8008). Store:
  `identity/store.py` (`AccountStore`, in-memory); persistence:
  `identity/persistence.py` (Redis snapshot); seeding: `identity/bootstrap.py`.
- Rewards model: `aoep_shared/rewards.py` (`PointsLedger`, `REWARDS_CATALOG`,
  `PrizeKind`, `points_for_completion`, `redeem_prize`). Endpoints: `/rewards`,
  `/rewards/catalog`, `/rewards/redeem`, `/rewards/grant` (HMAC-signed AI grants).
- Membership: `aoep_shared/membership.py` — `membership_class_for_tier(tier)`;
  only `tier == "premium"` maps to `"vip"`. Admins are seeded at PREMIUM (VIP).

## Durability (critical)
Identity keeps accounts/points/students in RAM and **snapshots the whole store to
Redis** after each mutation (`persist_hook`), and hydrates on boot. Redis is a
**system of record**, not a cache. Requirements (see `infra/k8s/redis.yaml`):
- Persistent volume + `--appendonly yes` (AOF) + RDB save points.
- `--maxmemory-policy volatile-lru` so only TTL'd keys (rate-limit, arcade rounds)
  can be evicted and the no-TTL `aoep:identity:v1:state` snapshot never is.
If a redeploy "loses points / re-pops the onboarding survey / resets admin", the
cause is almost always non-durable Redis (or a stale image) — not app logic.
`onboarding_completed_at` on the StudentProfile is what suppresses the survey.

## Seeded accounts (recovery)
`bootstrap_accounts()` runs on startup (idempotent, force-syncs passwords):
- Admin: `admin@salareen.com` (username `admin`) / `DEFAULT_ADMIN_PASSWORD`
  (default `88888888`), `is_admin`, PREMIUM/VIP.
- QA personas: `qa-pro@salareen.com` / `qa3` etc. / `QA_ACCOUNTS_PASSWORD`
  (default `QaTest123`).
On VKE, reseed live pods with `scripts/k8s_reseed_accounts.sh` (writes Redis AND
ops-reseeds every identity pod; a side-process Redis write does NOT update running
uvicorn workers). 404 from `/admin/ops/reseed-seeded` = identity image too old →
redeploy.

## Admin & feature flags
- Feature flags are served by the **memory** service; overrides are in-memory
  per replica (`aoep_shared/flags.py`). The `/admin` web page unlocks either by
  logging in as an admin account (auto) OR by the **ADMIN_SECRET** (sent as
  `X-Admin-Secret`). Default `dev-admin-secret`; an EMPTY expected secret rejects
  all (see `require_admin`), so a blank `ADMIN_SECRET` disables the secret box —
  use the admin-account path. Read the deployed value:
  `kubectl -n aoep get configmap aoep-config -o jsonpath='{.data.ADMIN_SECRET}'`.
- Flush flag overrides to catalog defaults: restart the memory deployment.

## Gotchas
- The full pytest suite clobbers the real mobile version files (see
  run-and-test-locally) — unrelated to identity but bites when committing.
- Raising raffle/prize costs or adding prizes: edit `REWARDS_CATALOG`; the web
  `/rewards` page fetches `/rewards/catalog` dynamically (no hardcoding), and the
  catalog payload includes `kind_label` for display.
