apps/mobile — Salareen mobile app (Expo SDK 51, iOS + Android)
=============================================================

Purpose
  React Native app: Netflix-style home rails, Drive Mode (voice profiles, "Hey
  Sala", opt-in driving detection), Salareen live rooms (LiveKit), Live Class
  (solo 1:1 + group), careers, rewards/arcade, notifications, and a 27-language
  locale picker (14 fully translated UI locales). The signed-in learner's
  language is adopted from and saved to their account.

Config
  Backend URLs come from apps/mobile/src/config.ts (cloud origin + path prefixes
  like /identity, /curriculum, /speech, or per-service local ports). On a
  physical Android device use `adb reverse` so it can reach Metro/backends.

Run (dev)
  cd apps/mobile && pnpm install
  pnpm run dev            # Metro; or dev:ios / dev:android
  (Makefile: make mobile-dev-ios / make mobile-dev-android)

Checks
  pnpm run typecheck      # make mobile-typecheck
  pnpm test               # Jest (make mobile-test path via make test)
  pnpm run export         # static JS bundle export (make mobile-build)

Native / EAS builds
  Android DEBUG (dev): pnpm run native:build:android  -> assembleDebug. Needs a
    reachable Metro (dev server); a standalone install shows the red "Unable to
    load script / index.android.bundle" screen. Use for live-reload development.
  Android PRODUCTION/RELEASE (standalone, local): pnpm run native:build:android:release
    -> fresh `gradle clean assembleRelease` with the JS bundle EMBEDDED (no Metro,
    backend pinned to cloud), verified by mobile-verify-apk-bundle.sh, published to
    dist/android/salareen-<version>-<versionCode>-release.apk. This is the
    "just works on any device" build (the Android equivalent of the iOS TestFlight
    build). Install: adb install -r dist/android/salareen-*-release.apk
  EAS profiles: development (dev client, needs Metro), preview (release APK,
    standalone), production (app bundle / IPA).

See also: apps/mobile/RUN.txt (full setup/run/debug), README.md
("Mobile app on macOS"), .cursor/rules/mobile-eas-build.mdc.
