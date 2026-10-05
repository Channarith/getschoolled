import { Image, type ImageStyle, type StyleProp } from "react-native";

import { avatarImageSource, getAvatar } from "../avatars";

type Props = {
  avatarId?: string | null;
  size?: number;
  style?: StyleProp<ImageStyle>;
  accessibilityLabel?: string;
};

export default function AvatarImage({
  avatarId,
  size = 40,
  style,
  accessibilityLabel,
}: Props) {
  const entry = getAvatar(avatarId);
  return (
    <Image
      source={avatarImageSource(avatarId)}
      accessibilityLabel={accessibilityLabel || entry.alt}
      style={[
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: "rgba(255,255,255,0.06)",
        },
        style,
      ]}
    />
  );
}
