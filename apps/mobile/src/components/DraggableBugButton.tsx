import { StyleSheet, Text } from "react-native";

import DraggableFloatingButton from "./DraggableFloatingButton";

const BUTTON_SIZE = 42;

interface Props {
  onPress: () => void;
  disabled?: boolean;
  aboveTabs?: boolean;
}

export default function DraggableBugButton({ onPress, disabled, aboveTabs }: Props) {
  return (
    <DraggableFloatingButton
      accessibilityLabel="Report a bug"
      aboveTabs={aboveTabs}
      disabled={disabled}
      height={BUTTON_SIZE}
      onPress={onPress}
      style={styles.container}
      width={BUTTON_SIZE}
    >
      <Text style={styles.icon}>🐛</Text>
    </DraggableFloatingButton>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: BUTTON_SIZE / 2,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(30,27,75,0.82)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.3)",
    shadowColor: "#000",
    shadowOpacity: 0.28,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    opacity: 0.82,
  },
  icon: { fontSize: 19 },
});
