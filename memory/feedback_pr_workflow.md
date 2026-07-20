---
name: feedback-pr-workflow
description: User prefers PR-based workflow — never commit directly to main
metadata:
  type: feedback
---

Always open a pull request instead of committing directly to main.

**Why:** User explicitly requested this so changes can be tracked, reviewed, and discussed before merging.

**How to apply:** For every feature or fix:
1. `git checkout -b <type>/<short-description>` from the latest main
2. Make commits on the branch
3. `git push -u origin <branch>` then `gh pr create` to open the PR
4. Never push commits directly to `origin/main`

Exception: version bumps and changelog entries that CI requires ON the PR branch are fine as branch commits.
