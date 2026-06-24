import { useEffect, useState } from "react";
import { Image, Text, View, type ImageSourcePropType, type ViewStyle } from "react-native";

import { resolveMascot } from "../api";
import { mascotImageForLocale, resolveMascotLocal } from "../mascot";
import { useT } from "../i18n";

type Props = {
  width?: number;
  height?: number;
  style?: ViewStyle;
  showCaption?: boolean;
};

/** Locale-aware photo-realistic Bayon Buddy mascot (ux.locale_mascots flag). */
export default function MascotSvg({ width = 220, height, style, showCaption = false }: Props) {
  const { locale } = useT();
  const [source, setSource] = useState<ImageSourcePropType>(() => mascotImageForLocale(locale));
  const [caption, setCaption] = useState("");

  useEffect(() => {
    let cancelled = false;
    resolveMascot(locale)
      .then((res) => {
        if (cancelled) return;
        setSource(mascotImageForLocale(res.locale, { enabled: res.enabled }));
        if (res.variant?.cultural_theme) setCaption(res.variant.cultural_theme);
        else setCaption("");
      })
      .catch(() => {
        if (cancelled) return;
        const local = resolveMascotLocal(locale);
        setSource(mascotImageForLocale(local.locale));
      });
    return () => { cancelled = true; };
  }, [locale]);

  return (
    <View style={[{ alignItems: "center" }, style]}>
      <Image
        source={source}
        style={{ width, height: height ?? Math.round(width * (512 / 250)), resizeMode: "contain" }}
        accessibilityLabel="Salareen Bayon Buddy mascot"
      />
      {showCaption && caption ? (
        <Text style={{ color: "#9aa6c2", fontSize: 13, marginTop: 6, textAlign: "center" }}>
          {caption}
        </Text>
      ) : null}
    </View>
  );
}
