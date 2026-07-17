import { registerRootComponent } from "expo";

import { ensureTextEncodingGlobals } from "./src/polyfills/textEncoding";

// Install before any lazy LiveKit require; Hermes lacks TextDecoder globally.
ensureTextEncodingGlobals();

import App from "./App";

registerRootComponent(App);
