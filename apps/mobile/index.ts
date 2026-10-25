import { registerRootComponent } from "expo";

import { ensureLiveKitGlobals } from "./src/polyfills/liveKitGlobals";
// Install client-side instrumentation BEFORE any Provider mounts, so a
// throw during e.g. LocaleProvider / AuthProvider is captured by the global
// error handler and written to the durable on-device crash file. Previously
// this was wired from a useEffect inside AppInner, which runs AFTER the
// Providers' first render — too late to see their mount errors.
import { installClientLog } from "./src/clientLog";
import { initSentry } from "./src/sentryHook";
import { initDiag } from "./src/diag/diagLog";
import { APP_VERSION } from "./src/version";

installClientLog();
void initDiag();   // camera/WebView triage log: restores the last session, notes this launch
// Sentry is DSN-gated and dynamically required — no-op if the package isn't
// installed or SENTRY_DSN isn't set. See src/sentryHook.ts for activation.
initSentry(APP_VERSION);

// Hermes (iOS + Android) lacks TextEncoder/TextDecoder before LiveKit loads.
ensureLiveKitGlobals();

import App from "./App";

registerRootComponent(App);
