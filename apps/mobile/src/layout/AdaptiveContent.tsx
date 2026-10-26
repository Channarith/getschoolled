import { View, type ViewProps } from "react-native";

import { useLayoutMetrics } from "./useLayoutMetrics";

type Props = ViewProps & {
  /** When false, content spans the full window width (still respects horizontal padding). */
  center?: boolean;
  /** Edge-to-edge. Games, audio, and the webcam use the whole display. */
  bleed?: boolean;
};

/** Centers readable content on expanded widths; full-bleed on phones. */
export default function AdaptiveContent({
  children,
  style,
  center = true,
  bleed = false,
  ...rest
}: Props) {
  const { contentMaxWidth, horizontalPadding } = useLayoutMetrics();
  return (
    <View
      style={[
        {
          width: "100%",
          maxWidth: bleed || !center ? undefined : contentMaxWidth,
          alignSelf: bleed || !center ? undefined : "center",
          paddingHorizontal: bleed ? 0 : horizontalPadding,
        },
        style,
      ]}
      {...rest}
    >
      {children}
    </View>
  );
}
