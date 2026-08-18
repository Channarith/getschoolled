// Dual-mode aware client: the orchestrator base URL is injected by config/env
// (local docker compose vs cloud ingress). No code changes between modes.
//
// This module is imported by CLIENT components, so only NEXT_PUBLIC_* vars are
// ever inlined — the bare ORCHESTRATOR_URL was never visible in the browser
// and the localhost fallback always won in production. Mirror the resolution
// used by app/lib/api.ts: explicit NEXT_PUBLIC override, then the same-origin
// /orchestrator prefix on deployed hosts, then localhost for dev.
function _orchestratorUrl(): string {
  if (process.env.NEXT_PUBLIC_ORCHESTRATOR_URL) {
    return process.env.NEXT_PUBLIC_ORCHESTRATOR_URL;
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host !== "localhost" && host !== "127.0.0.1" && host !== "::1") {
      return "/orchestrator";
    }
  }
  return "http://localhost:8000";
}

export const ORCHESTRATOR_URL = _orchestratorUrl();

export const DEPLOY_MODE =
  process.env.NEXT_PUBLIC_DEPLOY_MODE ?? process.env.DEPLOY_MODE ?? "local";

export type ClassType = "solo" | "group";

export interface JoinInfo {
  room: string;
  identity: string;
  token: string;
  url: string;
}

export async function fetchJoinToken(
  room: string,
  identity: string,
): Promise<JoinInfo> {
  const url = new URL(`${ORCHESTRATOR_URL}/classes/${room}/join`);
  url.searchParams.set("identity", identity);
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch join token: ${res.status}`);
  }
  return (await res.json()) as JoinInfo;
}
