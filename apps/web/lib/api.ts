// Dual-mode aware client: the orchestrator base URL is injected by config/env
// (local docker compose vs cloud ingress). No code changes between modes.

export const ORCHESTRATOR_URL =
  process.env.ORCHESTRATOR_URL ?? "http://localhost:8000";

export const DEPLOY_MODE = process.env.DEPLOY_MODE ?? "local";

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
