"use client";

/**
 * Renders an animated certification storyboard (SVG scene) for DMV / food-handler
 * slides. Inline SVG is required so CSS camera/cast keyframes actually play
 * (they do not run reliably when the same markup is loaded via <img>).
 */

type Props = {
  svg: string;
  concept?: string;
  sceneId?: string;
  fullscreen?: boolean;
};

export default function CourseStoryboardPlayer({
  svg,
  concept,
  sceneId,
  fullscreen = false,
}: Props) {
  if (!svg) return null;
  return (
    <figure
      className="course-storyboard"
      data-scene={sceneId || undefined}
      style={{
        margin: fullscreen ? "8px 0 16px" : "10px 0 14px",
        width: "100%",
        maxWidth: fullscreen ? 980 : 720,
        borderRadius: 12,
        overflow: "hidden",
        background: "linear-gradient(160deg, #0b1220 0%, #1e293b 55%, #0f766e 140%)",
        boxShadow: fullscreen
          ? "0 12px 40px rgba(0,0,0,0.45)"
          : "0 6px 20px rgba(15,23,42,0.18)",
      }}
    >
      <div
        aria-label={concept || "Course storyboard animation"}
        style={{ width: "100%", lineHeight: 0 }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      {concept ? (
        <figcaption
          style={{
            fontSize: fullscreen ? 15 : 13,
            color: fullscreen ? "#cbd5e1" : "#475569",
            padding: "8px 12px 10px",
            background: fullscreen ? "rgba(15,23,42,0.85)" : "rgba(248,250,252,0.95)",
          }}
        >
          {concept}
        </figcaption>
      ) : null}
    </figure>
  );
}
