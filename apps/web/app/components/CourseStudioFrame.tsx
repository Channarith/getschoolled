"use client";

export function CourseStudioFrame({ src, title }: { src: string; title: string }) {
  return (
    <iframe
      title={title}
      src={src}
      style={{
        width: "100%",
        height: "min(78vh, 820px)",
        border: "1px solid rgba(165,180,252,.35)",
        borderRadius: 16,
        background: "#fff",
      }}
    />
  );
}
