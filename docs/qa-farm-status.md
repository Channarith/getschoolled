# QA / Test Automation Farm — Status

_Snapshot of the automated-testing build-out (web Playwright + mobile jest/contract/Maestro).
Last updated: 2026-07-15 (main @ v0.19.56)._

This tracks what's automated, where it runs, whether it blocks a PR, what it should
be promoted to next, and how many automated tests back it. It complements the
V&V master plan (`docs/vv-master-plan.md`) — this is the "what's actually wired
and running" view.

## Status table

| Area | Status | When | Gate PR If Failed | Next to Promote | # of Automated Tests |
|---|---|---|---|---|---|
| Web Playwright (core specs + overflow) | ✅ live; `web-e2e` nightly builds + runs green | Nightly + manual dispatch | ❌ No — non-blocking | After ~2 wks green, lift into a required `ci.yml` job | **42** Playwright cases (13 spec files) |
| Mobile jest unit tier | ✅ live (`mobile-tests`) | On PR (`apps/mobile/**`) + push + dispatch | ❌ No — runs on PR, not yet required | Fold `pnpm test:ci` into `ci.yml`'s `mobile` job so it gates | **43** jest cases (6 suites) |
| Mobile contract test (K-API-1) | ✅ live in the python CI job | **Every PR + push** (inside `ci.yml`) | ✅ **Yes** — part of `ci.yml`, blocks automerge | — already gating | **59** parametrized cases (58 endpoints + manifest) |
| Mobile bundle-secret-scan (B-SEC-1) | ✅ passing in real CI | Nightly + dispatch (`mobile-e2e`) | ❌ No — non-blocking | Keep nightly (needs a prod export); PR-side regression already guarded by `config.test.ts` | **1** scan gate (4 credential patterns) |
| Mobile Maestro — seeded backend + plumbing | ✅ proven on the runner | Nightly + dispatch | ❌ No | n/a — infra for the Maestro legs | — (infra) |
| **Mobile Maestro — Android APK build** | 🟡 wired via EAS + merged (#283) → blocked on Expo quota, then verify | Nightly + dispatch | ❌ No | Fix Expo quota → verify green → then promote | **2** Maestro flows (`auth-login`, `drive-mode-happy`) |
| Mobile Maestro — iOS | ⏸️ **skipped** (wiring in place; needs a seeded backend) | Nightly + dispatch (when enabled) | ❌ No | Provide a seeded non-prod backend + set `MOBILE_E2E_IOS=true` | **2** Maestro flows (shared with Android) |
| web-e2e compose build | ✅ fixed (#233) | Nightly + dispatch (part of `web-e2e`) | ❌ No | n/a — infra; promotes with `web-e2e` | — (infra) |

**Automated total: ~144 test cases** (42 web Playwright + 43 jest + 59 contract) plus **2 Maestro flows** and **1 bundle-secret-scan gate**.

## Gating model (why only one row says "Yes")

The repo's automerge waits on the **`ci.yml`** workflow. So a check only blocks a PR
if it runs *inside* `ci.yml`. Today that's the backend `pytest` job — which is why the
**contract test (K-API-1)** is the only automated suite here that gates PRs (it lives in
`qa/tests/`, globbed by that job).

Everything else runs as its **own workflow** (`web-e2e`, `mobile-tests`, `mobile-e2e`) on
its own schedule. A red result there is informational — it does **not** stop a merge.
This is intentional: the plan's philosophy is **land non-blocking → burn in for
stability → promote to a required gate** once flake rate is low.

## Promotion roadmap

Ordered by readiness (green + stable first):

1. **jest unit tier → PR gate.** Fold `pnpm test:ci` into `ci.yml`'s existing `mobile`
   job (currently typecheck-only). Cheapest, highest-value promotion — makes mobile
   logic + the B-SEC-1 credential regression block merges like the contract test does.
2. **web-e2e / Playwright → PR gate.** After ~2 weeks of green nightlies (flake < 2%),
   lift its steps into a required `ci.yml` job (per the V&V plan's UI gate).
3. **Maestro (Android) → keep non-blocking** until it's actually green end-to-end
   (needs the Expo quota resolved + a first verify pass). Promote only after it's proven.
4. **Maestro (iOS) → enable first, promote later** — see open items.

## Open items (both are infra/account, not code)

1. **Android Maestro — Expo build quota.** The EAS Android build wiring is merged (#283)
   but the build itself failed on first dispatch (~1 min) with a billing/quota warning on
   the `cvanthin978` Expo account. Everything up to the cloud build works (auth, config
   resolution, keystore, upload, submission). Resolve at
   https://expo.dev/accounts/cvanthin978/settings/billing, then re-run `mobile-e2e`. The
   first real run will likely need a verify/tidy pass (APK download parsing, `adb install`,
   and **Maestro selector drift** vs the newer 0.19 UI).
2. **iOS Maestro — needs a reachable backend.** The iOS Simulator only runs on a macOS
   runner, and macOS runners **can't run Linux Docker**, so there's no local seeded backend
   there. The wiring is done (job gated behind `vars.MOBILE_E2E_IOS` + `MOBILE_E2E_CLOUD_URL`).
   To enable: either (a) point it at a **seeded, non-production QA cloud env** (set those two
   repo variables), or (b) run the Python services natively (uvicorn) on the macOS runner.
   Deferred by choice — Android E2E already covers the shared React Native logic; iOS adds
   value mainly for iOS-specific rendering/behavior.

## Where the suites live

- Web Playwright: `apps/web/e2e/**` — workflow `.github/workflows/web-e2e.yml`
- Mobile jest: `apps/mobile/src/__tests__/**` — workflow `.github/workflows/mobile-tests.yml`
- Contract test: `qa/tests/test_mobile_contract.py` + manifest `apps/mobile/contract/endpoints.json` — runs in `.github/workflows/ci.yml` (python job)
- Bundle-secret-scan: `apps/mobile/scripts/mobile-bundle-scan.sh` — job in `.github/workflows/mobile-e2e.yml`
- Maestro flows: `apps/mobile/.maestro/*.yaml` — jobs in `.github/workflows/mobile-e2e.yml`
