import { registerRootComponent } from "expo";

import { ensureLiveKitGlobals } from "./src/polyfills/liveKitGlobals";

// Hermes (iOS + Android) lacks TextEncoder/TextDecoder before LiveKit loads.
ensureLiveKitGlobals();

import App from "./App";

registerRootComponent(App);
