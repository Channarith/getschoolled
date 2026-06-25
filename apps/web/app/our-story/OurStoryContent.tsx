"use client";

import Image from "next/image";
import Link from "next/link";

import { LANGUAGE_LIST } from "../lib/i18n-strings";
import { useT } from "../lib/i18n";

const LANG_TOTAL = LANGUAGE_LIST.length;
const LANG_FULL = LANGUAGE_LIST.filter((l) => l.tier === "full").length;

const TOOL_KEYS = [
  "tutor", "homework", "humanLoop", "live", "drive", "mobile", "adaptive",
  "vision", "arcade", "scraper", "rag", "integrations", "languages", "robot",
] as const;

export default function OurStoryContent() {
  const { t } = useT();

  return (
    <main className="container" style={{ maxWidth: 880 }}>
      <h1>{t("story.title")}</h1>
      <p className="muted" style={{ fontSize: 18 }}>
        {t("story.lead")}
      </p>

      <div style={{ display: "flex", justifyContent: "center", margin: "20px 0" }}>
        <Image
          src="/salareen-mascot.webp"
          alt="Salareen study buddy"
          width={512}
          height={341}
          style={{ width: "min(320px, 70%)", height: "auto" }}
          priority
        />
      </div>

      <h2>{t("story.believeTitle")}</h2>
      <p>{t("story.believeBody")}</p>

      <h2>{t("story.nameTitle")}</h2>
      <p>
        <strong>Salareen</strong> comes from the Khmer <em>salaa rian</em> — “to
        go to school.” Our study buddy is a friendly, <strong>secular</strong>{" "}
        character inspired by classical Khmer craftsmanship, drawn as a modern
        mascot. Its silhouette forms an <strong>“S”</strong> for Salareen, with a
        stylized <strong>leaf of knowledge</strong> beside it.
      </p>

      <h2>{t("story.platformTitle")}</h2>
      <p>{t("story.platformBody")}</p>

      <div style={{ display: "flex", justifyContent: "center", margin: "16px 0" }}>
        <Image
          src="/salareen-ecosystem.webp"
          alt="Salareen platform map"
          width={1536}
          height={1024}
          style={{ width: "100%", height: "auto", borderRadius: 12 }}
        />
      </div>

      <p className="muted">{t("story.toolsHint")}</p>
      <ul className="tools">
        {TOOL_KEYS.map((key) => (
          <li
            key={key}
            className="tool"
            tabIndex={0}
            aria-label={t(`story.tool.${key}.name`, key === "languages" ? { langTotal: LANG_TOTAL, langFull: LANG_FULL } : undefined)}
          >
            <span className="tool-name">
              {t(`story.tool.${key}.name`, key === "languages" ? { langTotal: LANG_TOTAL, langFull: LANG_FULL } : undefined)}
            </span>
            <span className="tool-tip" role="tooltip">
              <p>{t(`story.tool.${key}.desc`, key === "languages" ? { langTotal: LANG_TOTAL, langFull: LANG_FULL } : undefined)}</p>
              <span className="ex-label">{t("story.examples")}</span>
              <ul className="examples">
                <li>{t(`story.tool.${key}.ex0`)}</li>
                <li>{t(`story.tool.${key}.ex1`)}</li>
              </ul>
            </span>
          </li>
        ))}
      </ul>

      <h2>{t("story.buildTitle")}</h2>
      <ul style={{ lineHeight: 1.8 }}>
        <li><strong>{t("story.build.privacyTitle")}</strong> {t("story.build.privacyBody")}</li>
        <li><strong>{t("story.build.aiTitle")}</strong> {t("story.build.aiBody")}</li>
        <li><strong>{t("story.build.affordTitle")}</strong> {t("story.build.affordBody")}</li>
        <li><strong>{t("story.build.respectTitle")}</strong> {t("story.build.respectBody")}</li>
      </ul>

      <p style={{ marginTop: 24 }}>
        <Link href="/browse" style={{ marginRight: 16 }}>{t("story.browseLink")}</Link>
        <Link href="/transparency">{t("story.transparencyLink")}</Link>
      </p>
    </main>
  );
}

export { LANG_FULL, LANG_TOTAL };
