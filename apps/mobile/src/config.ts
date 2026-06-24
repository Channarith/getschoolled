// Resolve backend URLs for simulator vs physical device vs deployed cluster.
//
// iOS Simulator: localhost points at your Mac.
// Android Emulator: use 10.0.2.2 (host loopback), not localhost.
// Physical device: set expo.extra.*Url in app.json to your Mac LAN IP or prod host.

import { Platform } from "react-native";
import Constants from "expo-constants";

const extra = (Constants.expoConfig?.extra || {}) as Record<string, string>;

function hostFallback(port: number): string {
  const h = Platform.OS === "android" ? "10.0.2.2" : "localhost";
  return `http://${h}:${port}`;
}

function serviceUrl(key: string, port: number): string {
  const configured = extra[key];
  if (configured && configured.startsWith("http")) return configured.replace(/\/$/, "");
  return hostFallback(port);
}

export const CURRICULUM_URL = serviceUrl("curriculumUrl", 8005);
export const IDENTITY_URL = serviceUrl("identityUrl", 8008);
export const MEMORY_URL = serviceUrl("memoryUrl", 8004);

export const QA_TEST_ACCOUNTS = [
  { label: "QA Pro", email: "qa-pro@salareen.com", password: "QaTest123" },
  { label: "QA3", email: "qa3", password: "QaTest123" },
  { label: "Admin", email: "admin@salareen.com", password: "88888888" },
] as const;
