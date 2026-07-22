import { StyleSheet, Text } from "react-native";

import DraggableFloatingButton from "./DraggableFloatingButton";

const BUTTON_WIDTH = 132;
const BUTTON_HEIGHT = 42;

type Props = {
  aboveTabs?: boolean;
  onPress: () => void;
};

export default function DraggableSalesDemoButton({ aboveTabs, onPress }: Props) {
  return (
    <DraggableFloatingButton
      accessibilityLabel="Open sales demo"
      aboveTabs={aboveTabs}
      height={BUTTON_HEIGHT}
      initialSide="left"
      onPress={onPress}
      style={styles.button}
      testID="sales-demo-button"
      width={BUTTON_WIDTH}
    >
      <Text style={styles.text}>✨ Sales Demo</Text>
    </DraggableFloatingButton>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: "center",
    backgroundColor: "rgba(30,27,75,0.92)",
    borderColor: "rgba(165,180,252,0.58)",
    borderRadius: BUTTON_HEIGHT / 2,
    borderWidth: 1,
    justifyContent: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.28,
    shadowRadius: 8,
  },
  text: {
    color: "#c7d2fe",
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0.3,
  },
});
