---
name: feedback-ci-before-push
description: Always run tests locally before pushing; new code that changes behavior must have test coverage checked
metadata:
  type: feedback
---

Before opening or pushing to a PR, run the Python test suite locally to catch regressions:

```bash
cd /Users/cvanthin/getschoolled
python -m pytest packages/shared/tests/ services/*/tests/ scripts/tests/ -x -q 2>&1 | tail -20
```

**Why:** PRs have repeatedly broken existing tests because:
1. New behavior guards (e.g. survey duplicate check) conflicted with tests that submit anonymously
2. Security hardening (e.g. removing X-User-Id from rate limiter) broke tests that relied on user-id isolation
3. Version bump threshold changes not reflected in both the script and tests
4. Missing package.json deps (e.g. @react-navigation/native imported but not listed)

**How to apply:**
- After writing any fix that changes validation, auth, or error behavior — grep for existing tests of that endpoint/function first
- When adding duplicate guards, check if tests submit without a student_id (anonymous submissions must be allowed through)
- When changing rate limiting identity, check test_service_scaling.py
- When importing a new npm package in mobile, add it to apps/mobile/package.json
- Always run `python3 scripts/bump_pr_version.py` before the first push (version-bump CI requires it)

**Key invariants that have broken CI before:**
- Survey submit: anonymous (no student_id) submissions must always succeed; deduplicate by (course_id, student_id) only when student_id is present
- Rate limit: keyed by IP, not X-User-Id (which users control); tests must not rely on header-based isolation
- DEFAULT_MINOR_BUMP_THRESHOLD = 120 (not 8); test suite expects 120-item threshold
- @react-navigation/native is NOT in the mobile package.json; use useEffect cleanup instead
