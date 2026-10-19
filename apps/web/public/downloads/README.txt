Salareen web downloads directory.

This folder is served at `/downloads/*` by the Next.js app. It holds large
installer artifacts (currently just the Android APK) that are too big to track
in git.

Staging happens BEFORE `docker build apps/web`:

  ./scripts/stage_apk_for_web.sh

The script copies the newest `salareen-*-release.apk` from
`apps/mobile/dist/android/` into this folder as BOTH:

  salareen-latest.apk               <-- stable URL the "Get the app" button hits
  salareen-<version>-<buildCode>-release.apk   <-- versioned filename kept for history

The web Dockerfile `COPY apps/web/public /app/public` picks them up at build
time, so once staged + rebuilt, the APK ships inside the image and no object
storage round-trip is required.

The .apk files are gitignored (see .gitignore `apps/web/public/downloads/*.apk`)
so this README is the only tracked file. Rebuild = re-run the stage script.
