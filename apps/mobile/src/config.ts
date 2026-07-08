// Resolve backend URLs for simulator, physical device, and deployed cluster.
//
// deployMode=cloud (default): primary https://www.salareen.com + path prefixes;
//   on network/5xx failure retries the Vultr failover (http://45.63.91.80 + same paths).
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

/** Direct Vultr cluster IP — used when www.salareen.com is unreachable. */
export const CLOUD_FAILOVER_BASE_URL = (
  extra.cloudFailoverBaseUrl || "http://45.63.91.80"
).replace(/\/$/, "");

/** Map a primary cloud service URL to its Vultr failover twin (cloud mode only). */
export function failoverUrlFor(primaryBase: string): string | null {
  if (DEPLOY_MODE !== "cloud") {
    return null;
  }
  const base = primaryBase.replace(/\/$/, "");
  const primary = CLOUD_BASE_URL;
  if (!base.startsWith(primary)) {
    return null;
  }
  return `${CLOUD_FAILOVER_BASE_URL}${base.slice(primary.length)}`;
}

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
export const ORCHESTRATOR_URL = serviceUrl("orchestratorUrl", 8000, "");
export const BILLING_URL = serviceUrl("billingUrl", 8006, "/billing");
export const SPEECH_URL = serviceUrl("speechUrl", 8002, "/speech");

export const QA_TEST_ACCOUNTS = [
  { label: "QA Pro", email: "qa-pro@salareen.com", password: "QaTest123" },
  { label: "QA3", email: "qa3", password: "QaTest123" },
  { label: "Admin", email: "admin@salareen.com", password: "88888888" },
] as const;
