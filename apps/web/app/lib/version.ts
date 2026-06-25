// Single source of truth for the web app's displayed version.
// APP_VERSION is kept in sync with the repo VERSION file by
// scripts/build_release.py; NEXT_PUBLIC_APP_VERSION (set at build) overrides it
// when present (e.g. CI builds), so the running app always shows the real build.
const GENERATED_VERSION = "0.3.124";

export const APP_VERSION: string =
  process.env.NEXT_PUBLIC_APP_VERSION || GENERATED_VERSION;
