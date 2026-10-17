import { View, type ViewProps } from "react-native";

import { useLayoutMetrics } from "./useLayoutMetrics";

type Props = ViewProps & {
  /** When false, content spans the full window width (still respects horizontal padding). */
  center?: boolean;
};

/** Centers readable content on expanded widths; full-bleed on phones. */
export default function AdaptiveContent({
  children,
  style,
  center = true,
  ...rest
}: Props) {
  const { contentMaxWidth, horizontalPadding } = useLayoutMetrics();
  return (
    <View
      style={[
        {
          width: "100%",
          maxWidth: center ? contentMaxWidth : undefined,
          alignSelf: center ? "center" : undefined,
          paddingHorizontal: horizontalPadding,
        },
        style,
      ]}
      {...rest}
    >
      {children}
    </View>
  );
}
