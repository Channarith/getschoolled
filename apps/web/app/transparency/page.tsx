"use client";

import { useEffect, useState } from "react";
import { getDisclosure, type Disclosure } from "../lib/api";
import { useT } from "../lib/i18n";

export default function TransparencyPage() {
  const { t } = useT();
  const [disclosure, setDisclosure] = useState<Disclosure | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    getDisclosure()
      .then(setDisclosure)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main className="container">
      <h1>{t("transparency.title")}</h1>
      <p className="muted">{t("transparency.intro")}</p>

      {disclosure && (
        <div className="card" style={{ borderColor: "#6ea8fe" }}>
          <strong>{t("transparency.current")}</strong>
          <div className="muted">{disclosure.line}</div>
          <ul>
            <li>{t("transparency.instructor")} {disclosure.instructor} (AI: {String(disclosure.is_ai)})</li>
            <li>{t("transparency.model")} {disclosure.model_name}</li>
            <li>{t("transparency.persona")} {disclosure.persona}</li>
            <li>
              {t("transparency.humanOfRecord")}{" "}
              {disclosure.human_of_record ?? t("transparency.humanDefault")}
            </li>
          </ul>
        </div>
      )}
      {error && (
        <div className="card" style={{ borderColor: "#ff6b6b" }}>
          <div className="muted">{t("transparency.loadError")} {error}</div>
        </div>
      )}

      <div className="card">
        <h3>{t("transparency.aiDoes")}</h3>
        <ul>
          <li>{t("transparency.aiDoes1")}</li>
          <li>{t("transparency.aiDoes2")}</li>
          <li>{t("transparency.aiDoes3")}</li>
        </ul>
      </div>

      <div className="card">
        <h3>{t("transparency.humanStays")}</h3>
        <ul>
          <li>{t("transparency.human1")}</li>
          <li>{t("transparency.human2")}</li>
          <li>{t("transparency.human3")}</li>
        </ul>
      </div>

      <div className="card">
        <h3>{t("transparency.dataChoices")}</h3>
        <ul>
          <li>{t("transparency.data1")}</li>
          <li>{t("transparency.data2")}</li>
        </ul>
      </div>
    </main>
  );
}
