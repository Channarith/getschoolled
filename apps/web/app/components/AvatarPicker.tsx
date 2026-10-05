"use client";

import { useId, useMemo, useState } from "react";

import AvatarImage from "./AvatarImage";
import {
  AVATAR_STYLES,
  avatarsByStyle,
  getAvatar,
  resolveAvatarId,
  type AvatarStyle,
} from "../lib/avatars";

type Props = {
  value?: string | null;
  onChange: (avatarId: string) => void;
  disabled?: boolean;
  heading?: string;
  compact?: boolean;
};

export default function AvatarPicker({
  value,
  onChange,
  disabled,
  heading = "Choose your avatar",
  compact = false,
}: Props) {
  const selected = resolveAvatarId(value);
  const selectedEntry = getAvatar(selected);
  const [style, setStyle] = useState<AvatarStyle>(selectedEntry.style);
  const baseId = useId();
  const items = useMemo(() => avatarsByStyle(style), [style]);

  return (
    <section
      aria-labelledby={`${baseId}-heading`}
      style={{
        display: "grid",
        gap: compact ? 10 : 14,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <AvatarImage avatarId={selected} size={compact ? 56 : 72} />
        <div>
          <h2
            id={`${baseId}-heading`}
            style={{ margin: 0, fontSize: compact ? 16 : 18, fontWeight: 750 }}
          >
            {heading}
          </h2>
          <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: 13 }}>
            {selectedEntry.label} · {selectedEntry.style === "realistic" ? "Realistic" : "Cute"}
          </p>
        </div>
      </div>

      <div
        role="tablist"
        aria-label="Avatar style"
        style={{ display: "flex", gap: 8, flexWrap: "wrap" }}
      >
        {AVATAR_STYLES.map((s) => {
          const active = style === s.id;
          return (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={active}
              disabled={disabled}
              onClick={() => setStyle(s.id)}
              style={{
                border: active ? "2px solid var(--accent, #f59e0b)" : "1px solid var(--border)",
                background: active ? "rgba(245,158,11,0.12)" : "transparent",
                color: "var(--text)",
                borderRadius: 999,
                padding: "8px 14px",
                cursor: disabled ? "not-allowed" : "pointer",
                fontWeight: active ? 700 : 550,
                fontSize: 13,
              }}
            >
              {s.label}
            </button>
          );
        })}
      </div>

      <div
        role="listbox"
        aria-label={`${style === "realistic" ? "Realistic" : "Cute"} avatars`}
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(72px, 1fr))",
          gap: 10,
        }}
      >
        {items.map((entry) => {
          const isSelected = entry.id === selected;
          return (
            <button
              key={entry.id}
              type="button"
              role="option"
              aria-selected={isSelected}
              aria-label={entry.alt}
              disabled={disabled}
              onClick={() => onChange(entry.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onChange(entry.id);
                }
              }}
              style={{
                display: "grid",
                justifyItems: "center",
                gap: 6,
                padding: 8,
                borderRadius: 14,
                border: isSelected
                  ? "2px solid var(--accent, #f59e0b)"
                  : "1px solid var(--border)",
                background: isSelected ? "rgba(245,158,11,0.1)" : "var(--panel)",
                cursor: disabled ? "not-allowed" : "pointer",
                color: "var(--text)",
                boxShadow: isSelected ? "0 0 0 3px rgba(245,158,11,0.18)" : "none",
                transition: "border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease",
              }}
              onMouseEnter={(e) => {
                if (!disabled) e.currentTarget.style.transform = "translateY(-1px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "none";
              }}
            >
              <AvatarImage avatarId={entry.id} size={52} alt="" />
              <span style={{ fontSize: 12, fontWeight: 650 }}>{entry.label}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
