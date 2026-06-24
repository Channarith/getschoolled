import { useEffect, useState } from "react";
import { Text, View, type ViewStyle } from "react-native";
import { SvgXml } from "react-native-svg";

import { resolveMascot } from "../api";
import { mascotSvgForLocale, resolveMascotLocal } from "../mascot";
import { useT } from "../i18n";

type Props = {
  width?: number;
  height?: number;
  style?: ViewStyle;
  showCaption?: boolean;
};

/** Locale-aware Bayon Buddy mascot (gated by ux.locale_mascots flag). */
export default function MascotSvg({ width = 220, height = 360, style, showCaption = false }: Props) {
  const { locale } = useT();
  const [svg, setSvg] = useState(() => mascotSvgForLocale(locale));
  const [caption, setCaption] = useState("");

  useEffect(() => {
    let cancelled = false;
    resolveMascot(locale)
      .then((res) => {
        if (cancelled) return;
        setSvg(mascotSvgForLocale(res.locale, { enabled: res.enabled }));
        if (res.variant?.cultural_theme) setCaption(res.variant.cultural_theme);
        else setCaption("");
      })
      .catch(() => {
        if (cancelled) return;
        const local = resolveMascotLocal(locale);
        setSvg(mascotSvgForLocale(local.locale));
      });
    return () => { cancelled = true; };
  }, [locale]);

  return (
    <View style={[{ alignItems: "center" }, style]}>
      <SvgXml xml={svg} width={width} height={height} />
      {showCaption && caption ? (
        <Text style={{ color: "#9aa6c2", fontSize: 13, marginTop: 6, textAlign: "center" }}>
          {caption}
        </Text>
      ) : null}
    </View>
  );
}
