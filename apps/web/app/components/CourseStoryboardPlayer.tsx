"use client";

import { useEffect, useMemo, useState } from "react";
import { translateText } from "../lib/api";
import { useT } from "../lib/i18n";

/**
 * Renders an animated storyboard for any corporate or solo course.
 * Inline SVG is required so CSS camera/cast keyframes actually play
 * (they do not run reliably when the same markup is loaded via <img>).
 */

type Props = {
  svg: string;
  concept?: string;
  sceneId?: string;
  fullscreen?: boolean;
  translatedConcept?: string;
  examples?: string[];
  activity?: string;
  profileMode?: string;
  sourceLanguage?: string;
};

export default function CourseStoryboardPlayer({
  svg,
  concept,
  sceneId,
  fullscreen = false,
  translatedConcept,
  examples: examplesProp,
  activity,
  profileMode = "mixed",
  sourceLanguage = "en",
}: Props) {
  const examples = useMemo(() => examplesProp || [], [examplesProp]);
  const { locale } = useT();
  const [localized, setLocalized] = useState<{
    concept: string; examples: string[]; activity: string;
  } | null>(null);
  useEffect(() => {
    let active = true;
    if (translatedConcept || locale === sourceLanguage) {
      setLocalized(null);
      return () => { active = false; };
    }
    void Promise.all(
      [concept || "", ...examples, activity || ""].map(async (text) => {
        if (!text) return "";
        try { return (await translateText(text, sourceLanguage, locale)).text; }
        catch { return text; }
      }),
    ).then((values) => {
      if (!active) return;
      setLocalized({
        concept: values[0],
        examples: values.slice(1, 1 + examples.length),
        activity: values[1 + examples.length] || "",
      });
    });
    return () => { active = false; };
  }, [concept, examples, activity, locale, sourceLanguage, translatedConcept]);
  if (!svg) return null;
  const shownConcept = translatedConcept || localized?.concept || concept;
  const shownExamples = localized?.examples || examples;
  const shownActivity = localized?.activity || activity;
  return (
    <figure
      className="course-storyboard"
      data-scene={sceneId || undefined}
      data-profile-mode={profileMode}
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
        aria-label={shownConcept || "Course storyboard animation"}
        style={{ width: "100%", lineHeight: 0 }}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      {shownConcept ? (
        <figcaption
          style={{
            fontSize: fullscreen ? 15 : 13,
            color: fullscreen ? "#cbd5e1" : "#475569",
            padding: "8px 12px 10px",
            background: fullscreen ? "rgba(15,23,42,0.85)" : "rgba(248,250,252,0.95)",
          }}
        >
          <div>{shownConcept}</div>
          {shownConcept !== concept ? (
            <div style={{ color: "#94a3b8", marginTop: 3 }}>{concept}</div>
          ) : null}
          {shownExamples.length ? (
            <div style={{ marginTop: 7 }}>
              <strong>Examples:</strong> {shownExamples.join(" · ")}
            </div>
          ) : null}
          {shownActivity ? (
            <div style={{ marginTop: 7, color: fullscreen ? "#fde68a" : "#92400e" }}>
              🎯 {shownActivity}
            </div>
          ) : null}
        </figcaption>
      ) : null}
    </figure>
  );
}
