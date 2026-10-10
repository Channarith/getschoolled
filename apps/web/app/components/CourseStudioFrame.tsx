"use client";

import { ImmersiveFrame } from "./ImmersiveFrame";

export function CourseStudioFrame({ src, title }: { src: string; title: string }) {
  return (
    <ImmersiveFrame title={title}>
      <iframe
        title={title}
        src={src}
        allow="fullscreen; microphone; camera"
        style={{
          width: "100%",
          height: "100%",
          minHeight: "min(78vh, 820px)",
          border: "1px solid rgba(165,180,252,.35)",
          borderRadius: 16,
          background: "#fff",
        }}
      />
    </ImmersiveFrame>
  );
}
