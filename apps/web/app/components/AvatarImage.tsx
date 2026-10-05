"use client";

import { getAvatar, resolveAvatarId } from "../lib/avatars";

type Props = {
  avatarId?: string | null;
  size?: number;
  alt?: string;
  className?: string;
  style?: React.CSSProperties;
  title?: string;
};

/** Renders a catalog avatar (or polished default) as a circular image. */
export default function AvatarImage({
  avatarId,
  size = 40,
  alt,
  className,
  style,
  title,
}: Props) {
  const entry = getAvatar(avatarId);
  const label = alt || entry.alt;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- local SVG catalog; next/image adds little value
    <img
      src={entry.path}
      alt={label}
      title={title || entry.label}
      width={size}
      height={size}
      data-avatar-id={resolveAvatarId(avatarId)}
      className={className}
      draggable={false}
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        objectFit: "cover",
        display: "block",
        background: "var(--panel, #1e293b)",
        ...style,
      }}
    />
  );
}
