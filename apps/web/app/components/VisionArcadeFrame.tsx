"use client";

export function VisionArcadeFrame({ src, title }: { src: string; title: string }) {
  return (
    <iframe
      title={title}
      src={src}
      allow="camera; microphone; fullscreen"
      style={{
        width: "100%",
        height: "min(88vh, 980px)",
        border: "1px solid rgba(165,180,252,.35)",
        borderRadius: 16,
        background: "#0f172a",
      }}
    />
  );
}
