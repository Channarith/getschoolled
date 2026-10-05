import {
  AVATAR_CATALOG,
  DEFAULT_AVATAR_ID,
  LEGACY_AVATAR_ALIASES,
  type AvatarEntry,
  type AvatarStyle,
} from "./avatarCatalog";

export type { AvatarEntry, AvatarStyle };
export { AVATAR_CATALOG, DEFAULT_AVATAR_ID, LEGACY_AVATAR_ALIASES };

export const AVATAR_STYLES: { id: AvatarStyle; label: string; description: string }[] = [
  { id: "realistic", label: "Realistic", description: "Warm illustrated portraits" },
  { id: "cute", label: "Cute", description: "Friendly rounded characters" },
];

export function resolveAvatarId(avatarId?: string | null): string {
  const raw = (avatarId || "").trim().toLowerCase();
  if (raw in LEGACY_AVATAR_ALIASES) return LEGACY_AVATAR_ALIASES[raw];
  if (AVATAR_CATALOG.some((a) => a.id === raw)) return raw;
  for (const sep of [":", "/", "."] as const) {
    if (raw.includes(sep)) {
      const tail = raw.split(sep).pop() || "";
      if (tail in LEGACY_AVATAR_ALIASES) return LEGACY_AVATAR_ALIASES[tail];
      if (AVATAR_CATALOG.some((a) => a.id === tail)) return tail;
    }
  }
  return DEFAULT_AVATAR_ID;
}

export function getAvatar(avatarId?: string | null): AvatarEntry {
  const id = resolveAvatarId(avatarId);
  return AVATAR_CATALOG.find((a) => a.id === id) || AVATAR_CATALOG[0];
}

export function avatarSrc(avatarId?: string | null): string {
  return getAvatar(avatarId).path;
}

export function avatarsByStyle(style?: AvatarStyle | null): AvatarEntry[] {
  if (!style) return [...AVATAR_CATALOG];
  return AVATAR_CATALOG.filter((a) => a.style === style);
}

/** LocalStorage key for guests / optimistic UI before account sync. */
export const AVATAR_LOCAL_KEY = "aoep.avatar_id";

export function readLocalAvatarId(): string {
  if (typeof window === "undefined") return DEFAULT_AVATAR_ID;
  try {
    return resolveAvatarId(localStorage.getItem(AVATAR_LOCAL_KEY));
  } catch {
    return DEFAULT_AVATAR_ID;
  }
}

export function writeLocalAvatarId(avatarId: string): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(AVATAR_LOCAL_KEY, resolveAvatarId(avatarId));
  } catch {
    /* ignore */
  }
}
