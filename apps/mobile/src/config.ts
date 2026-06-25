// Resolve backend URLs for simulator, physical device, and deployed cluster.
//
// deployMode=cloud (default): same HTTPS origin + path prefixes as www.salareen.com
//   (https://www.salareen.com/identity, /curriculum, /memory).
// deployMode=local: iOS Simulator uses localhost; Android emulator uses 10.0.2.2.
// Override via MOBILE_DEPLOY_MODE / MOBILE_CLOUD_BASE_URL (see app.config.js).

import { Platform } from "react-native";
import Constants from "expo-constants";

const extra = (Constants.expoConfig?.extra || {}) as Record<string, string>;

export type DeployMode = "local" | "cloud";

export const DEPLOY_MODE: DeployMode =
  extra.deployMode === "local" ? "local" : "cloud";

export const CLOUD_BASE_URL = (
  extra.cloudBaseUrl || "https://www.salareen.com"
).replace(/\/$/, "");

function hostFallback(port: number): string {
  const h = Platform.OS === "android" ? "10.0.2.2" : "localhost";
  return `http://${h}:${port}`;
}

function mapLocalHostForAndroid(url: string): string {
  if (Platform.OS !== "android") {
    return url;
  }
  return url
    .replace("://localhost", "://10.0.2.2")
    .replace("://127.0.0.1", "://10.0.2.2");
}

function localServiceUrl(key: string, port: number): string {
  const configured = extra[key];
  if (configured && configured.startsWith("http")) {
    return mapLocalHostForAndroid(configured.replace(/\/$/, ""));
  }
  return hostFallback(port);
}

function cloudServiceUrl(servicePath: string, key: string): string {
  const configured = extra[key];
  if (configured && configured.startsWith("http") && !configured.includes("localhost")) {
    return configured.replace(/\/$/, "");
  }
  return `${CLOUD_BASE_URL}${servicePath}`;
}

function serviceUrl(key: string, port: number, cloudPath: string): string {
  if (DEPLOY_MODE === "cloud") {
    return cloudServiceUrl(cloudPath, key);
  }
  return localServiceUrl(key, port);
}

export const CURRICULUM_URL = serviceUrl("curriculumUrl", 8005, "/curriculum");
export const IDENTITY_URL = serviceUrl("identityUrl", 8008, "/identity");
export const MEMORY_URL = serviceUrl("memoryUrl", 8004, "/memory");

export const QA_TEST_ACCOUNTS = [
  { label: "QA Pro", email: "qa-pro@salareen.com", password: "QaTest123" },
  { label: "QA3", email: "qa3", password: "QaTest123" },
  { label: "Admin", email: "admin@salareen.com", password: "88888888" },
] as const;
