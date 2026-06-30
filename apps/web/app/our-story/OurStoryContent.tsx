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
    <main className="container" style={{ maxWidth: 900 }}>
      <article className="story">
        <h1 className="story-title">{t("story.title")}</h1>
        <p className="story-lead">{t("story.lead")}</p>

        <figure className="story-figure story-mascot">
          <Image
            src="/salareen-mascot.webp"
            alt="Salareen study buddy"
            width={512}
            height={341}
            style={{ width: "min(300px, 72%)", height: "auto" }}
            priority
          />
        </figure>

        <h2>{t("story.rootsTitle")}</h2>
        <p>{t("story.rootsBody1")}</p>
        <p>{t("story.rootsBody2")}</p>

        <h2>{t("story.nameTitle")}</h2>
        <p>
          <strong>Salareen</strong> comes from the Khmer <em>salaa rian</em> — “to
          go to school.” Our study buddy is a friendly, <strong>secular</strong>{" "}
          character inspired by classical Khmer craftsmanship, drawn as a modern
          mascot. Its silhouette forms an <strong>“S”</strong> for Salareen, with a
          stylized <strong>leaf of knowledge</strong> beside it.
        </p>

        <h2>{t("story.differentTitle")}</h2>
        <p>{t("story.differentBody")}</p>

        <h2>{t("story.platformTitle")}</h2>
        <p>{t("story.platformBody")}</p>

        <figure className="story-figure">
          <Image
            src="/salareen-ecosystem.webp"
            alt="Salareen platform map"
            width={1536}
            height={1024}
            style={{ width: "100%", height: "auto", borderRadius: 12 }}
          />
        </figure>

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

        <h2>{t("story.everyoneTitle")}</h2>
        <p>{t("story.everyoneBody")}</p>

        <h2>{t("story.buildTitle")}</h2>
        <ul className="story-build">
          <li><strong>{t("story.build.privacyTitle")}</strong> {t("story.build.privacyBody")}</li>
          <li><strong>{t("story.build.aiTitle")}</strong> {t("story.build.aiBody")}</li>
          <li><strong>{t("story.build.affordTitle")}</strong> {t("story.build.affordBody")}</li>
          <li><strong>{t("story.build.respectTitle")}</strong> {t("story.build.respectBody")}</li>
        </ul>

        <p className="story-links">
          <Link href="/browse">{t("story.browseLink")}</Link>
          <Link href="/transparency">{t("story.transparencyLink")}</Link>
        </p>
      </article>
    </main>
  );
}

export { LANG_FULL, LANG_TOTAL };
