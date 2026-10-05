import {
  AVATAR_CATALOG,
  AVATAR_IMAGES,
  DEFAULT_AVATAR_ID,
  LEGACY_AVATAR_ALIASES,
  type AvatarEntry,
  type AvatarStyle,
} from "./avatarCatalog";

export type { AvatarEntry, AvatarStyle };
export { AVATAR_CATALOG, AVATAR_IMAGES, DEFAULT_AVATAR_ID, LEGACY_AVATAR_ALIASES };

export const AVATAR_STYLES: { id: AvatarStyle; label: string; description: string }[] = [
  { id: "realistic", label: "Realistic", description: "Warm illustrated portraits" },
  { id: "cute", label: "Cute", description: "Friendly rounded characters" },
];

export function resolveAvatarId(avatarId?: string | null): string {
  const raw = (avatarId || "").trim().toLowerCase();
  if (Object.prototype.hasOwnProperty.call(LEGACY_AVATAR_ALIASES, raw)) {
    return LEGACY_AVATAR_ALIASES[raw];
  }
  if (AVATAR_CATALOG.some((a) => a.id === raw)) return raw;
  for (const sep of [":", "/", "."] as const) {
    if (raw.includes(sep)) {
      const tail = raw.split(sep).pop() || "";
      if (Object.prototype.hasOwnProperty.call(LEGACY_AVATAR_ALIASES, tail)) {
        return LEGACY_AVATAR_ALIASES[tail];
      }
      if (AVATAR_CATALOG.some((a) => a.id === tail)) return tail;
    }
  }
  return DEFAULT_AVATAR_ID;
}

export function getAvatar(avatarId?: string | null): AvatarEntry {
  const id = resolveAvatarId(avatarId);
  return AVATAR_CATALOG.find((a) => a.id === id) || AVATAR_CATALOG[0];
}

export function avatarImageSource(avatarId?: string | null): number {
  const id = resolveAvatarId(avatarId);
  return AVATAR_IMAGES[id] || AVATAR_IMAGES[DEFAULT_AVATAR_ID];
}

export function avatarsByStyle(style?: AvatarStyle | null): AvatarEntry[] {
  if (!style) return [...AVATAR_CATALOG];
  return AVATAR_CATALOG.filter((a) => a.style === style);
}
