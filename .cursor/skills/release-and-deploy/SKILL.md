---
name: release-and-deploy
description: How to ship a change — version bumping, branch/PR/auto-merge conventions, and deploying to the Vultr Kubernetes (VKE) cluster. Use when cutting a release, bumping VERSION, opening/merging a PR, or deploying; and to avoid the classic "I deployed but the site still shows the old version / 404s" trap (stale images). Covers the changelog convention, the (removed) version gate, auto-merge requiring non-draft PRs, and the VKE image-build + reseed flow.
---

# Release & deploy

## Branch / commit / PR conventions
- Branch prefix `cursor/<desc>-<suffix>`; do not force-push/amend unless asked.
- `CHANGELOG.txt`: prepend a **dated** bullet (`- YYYY-MM-DD - …`, newest first).
  It uses a **union** merge driver (`.gitattributes`) so concurrent entries
  auto-combine — keep one bullet per change. Run `make git-setup` once per clone
  for the local merge drivers.
- No new markdown docs (use `docs/*.txt`); `python3` always; pin deps.

## Versioning
- `python3 scripts/bump_pr_version.py` — **patch by default** (0.14.13 → 0.14.14);
  `--force-level minor` for a deliberate feature release (0.15.0). Updates
  `VERSION`, `build-info.txt`, `apps/web/app/lib/version.ts` (+ web `package.json`)
  and the mobile version files.
- The old per-PR "VERSION must be bumped" CI gate was **removed** (it collided when
  concurrent PRs hit the same 0.x). Bumping is now optional/explicit; still bump
  for user-facing releases so the deployed version reflects the change.
- **Gotcha:** running the FULL pytest suite rewrites the real mobile version files
  to `0.3.82` (via `scripts/tests/test_bump_pr_version.py`). After a full run,
  `git checkout -- apps/mobile/{app.json,package.json,src/version.ts}` before commit.

## PRs & auto-merge
- Create PRs **non-draft** — the `automerge.yml` workflow squash-merges a PR after
  the CI workflow succeeds, but it CANNOT merge a draft ("Pull Request is still a
  draft"). It keeps the branch (no --delete-branch).
- `mobile-tests` CI is currently red for an unrelated global Jest/Babel transform
  issue; it's a separate (non-CI-workflow) check and does not block auto-merge.

## Deploy to Vultr (VKE)
- **One-command manual deploy (correct order):** `scripts/deploy_vke.sh` does
  build → push → apply → restart, never clobbers secrets, and skips the unused
  self-hosted LiveKit. Prefer it (or the `Deploy` GitHub workflow) over ad-hoc
  `kubectl` sequences. Export `VULTR_REGISTRY_USERNAME/PASSWORD` (and, on a fresh
  cluster, `LIVEKIT_API_KEY/SECRET`) first.
- **Secrets are managed OUT OF BAND:** `aoep-secrets` is NOT in the applied
  kustomization (so `apply -k` can't reset it to `__INJECT__`). Bootstrap once with
  `scripts/k8s_bootstrap_secrets.sh` (create-if-missing); template in
  `infra/k8s/aoep-secrets.example.yaml`. Rotate a single key with
  `kubectl -n aoep patch secret aoep-secrets --type merge -p '{"stringData":{...}}'`.
- **LiveKit is Cloud, not self-hosted:** `LIVEKIT_URL` in `configmap-vke.yaml`
  points at the LiveKit Cloud project; the in-cluster `livekit` Deployment/ingress
  is removed from the kustomization. `LIVEKIT_API_KEY/SECRET` (in `aoep-secrets`)
  must match that Cloud project (secret >= 32 chars).
- Manifests: `infra/k8s` (base) + `infra/k8s-vke` (overlay; images
  `sjc.vultrcr.com/salareen/*`, `LIVEKIT_URL` = the LiveKit Cloud project).
  Secrets/keys (`LIVEKIT_API_*`, `ADMIN_SECRET` overrides, `ELEVENLABS_API_KEY`,
  DB) are k8s Secrets; non-secret config is the `aoep-config` configmap.
- **Stale-image trap (the #1 "still 404 / old version" cause):** a plain
  `kubectl apply` does NOT rebuild/re-pull `:latest`. Ship code by running the
  **Deploy VKE (identity + web)** GitHub workflow (builds from `main`, pushes to
  the Vultr registry, rolls the deployments). Needs `VULTR_REGISTRY_USERNAME`,
  `VULTR_REGISTRY_PASSWORD`, `KUBE_CONFIG_B64`. Symptoms of a stale image: 404 on
  newer routes (e.g. `/identity/games/submit`, `/api/live-rooms/*`), nav shows an
  old `vX.Y.Z`. **Build FRESH — no layer cache:** `deploy_vke.sh` now builds with
  `--no-cache --pull` by default (a cache-hit once shipped an OLD orchestrator
  while the web updated → `/api/live-rooms/*` `start-presentation`/`media-token`/
  `tick` 404/405'd). After a deploy, CONFIRM the API updated: the script prints
  the orchestrator `/version` — it must equal the checkout's `VERSION`. If web
  shows a new version but the API 404/405s, the orchestrator image is stale.
- **`/orchestrator` etc. routing (405/404 on API POSTs):** the web calls
  same-origin `/orchestrator`, `/identity`, `/curriculum` … which the **`aoep-apis`
  Ingress** rewrites to each service. If `aoep-apis` is missing, those calls fall
  through to the web app (Next.js) → **405 Method Not Allowed** on POST (page is
  GET-only) or 404. Verify with `kubectl -n aoep get ingress aoep aoep-apis`;
  `deploy_vke.sh` now warns when it's absent. Re-`apply -k infra/k8s-vke` to
  restore it.
- Durable data: Redis must be durable (PV + AOF + volatile-lru, `infra/k8s/redis.yaml`)
  or identity accounts/points reset on restart. Reseed accounts after a fresh
  cluster/restart: `scripts/k8s_reseed_accounts.sh` (see identity-rewards-durability).
- Recreating the Redis StatefulSet with new `volumeClaimTemplates` needs a one-time
  `kubectl -n aoep delete statefulset redis --cascade=orphan && kubectl apply -k infra/k8s-vke`.
