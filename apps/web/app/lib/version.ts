// Single source of truth for the web app's displayed version.
// APP_VERSION is kept in sync with the repo VERSION file by
// scripts/build_release.py; NEXT_PUBLIC_APP_VERSION (set at build) overrides it
// when present (e.g. CI builds), so the running app always shows the real build.
<<<<<<< HEAD
const GENERATED_VERSION = "0.27.2";
=======
const GENERATED_VERSION = "0.27.2";
>>>>>>> c2d4f017 (Fix CI failures: update auto-minor threshold test to 120, remove dead summativeCompleted arg, bump to 0.26.2)

export const APP_VERSION: string =
  process.env.NEXT_PUBLIC_APP_VERSION || GENERATED_VERSION;
