import { useEffect, useRef } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";

import { AGE_MAX, AGE_MIN, AGE_OPTIONS, SETUP_COLORS, clampAge } from "../learnerCheck";

export const AGE_ROW_HEIGHT = 44;
const VISIBLE_ROWS = 5;
const START_AGE = 12;

type Props = {
  /** 0 while the learner has not picked an age yet. */
  value: number;
  onChange: (age: number) => void;
};

export function ageAtOffset(offsetY: number): number {
  return clampAge(AGE_MIN + Math.round(offsetY / AGE_ROW_HEIGHT));
}

/** A native snap-scrolling picker for ages 3–120 (no +/− steppers). */
export default function AgeWheel({ value, onChange }: Props) {
  const scrollRef = useRef<ScrollView>(null);
  const shown = value || START_AGE;

  useEffect(() => {
    scrollRef.current?.scrollTo({ y: (shown - AGE_MIN) * AGE_ROW_HEIGHT, animated: false });
    // Only on mount: later changes come from the wheel itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function settle(event: NativeSyntheticEvent<NativeScrollEvent>) {
    const age = ageAtOffset(event.nativeEvent.contentOffset.y);
    if (age !== value) onChange(age);
  }

  function select(age: number) {
    const next = clampAge(age);
    scrollRef.current?.scrollTo({ y: (next - AGE_MIN) * AGE_ROW_HEIGHT, animated: true });
    onChange(next);
  }

  return (
    <View
      style={styles.wrap}
      accessible
      accessibilityRole="adjustable"
      accessibilityLabel="Age"
      accessibilityValue={{ min: AGE_MIN, max: AGE_MAX, now: value || undefined, text: value ? `${value} years` : "Not chosen" }}
      accessibilityActions={[{ name: "increment" }, { name: "decrement" }]}
      onAccessibilityAction={(event) => {
        if (event.nativeEvent.actionName === "increment") select(shown + 1);
        if (event.nativeEvent.actionName === "decrement") select(shown - 1);
      }}
    >
      <View pointerEvents="none" style={styles.band} />
      <ScrollView
        ref={scrollRef}
        testID="age-wheel"
        showsVerticalScrollIndicator={false}
        snapToInterval={AGE_ROW_HEIGHT}
        decelerationRate="fast"
        nestedScrollEnabled
        contentContainerStyle={styles.content}
        onMomentumScrollEnd={settle}
        onScrollEndDrag={(event) => {
          if (!event.nativeEvent.velocity?.y) settle(event);
        }}
      >
        {AGE_OPTIONS.map((age) => {
          const on = age === value;
          return (
            <Pressable key={age} style={styles.row} onPress={() => select(age)} importantForAccessibility="no">
              <Text style={[styles.text, on && styles.textOn]}>{age}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
      <View pointerEvents="none" style={styles.unitWrap}>
        <Text style={styles.unit}>years</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: 150,
    height: AGE_ROW_HEIGHT * VISIBLE_ROWS,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: SETUP_COLORS.border,
    backgroundColor: SETUP_COLORS.panel,
    overflow: "hidden",
  },
  band: {
    position: "absolute",
    left: 8,
    right: 8,
    top: AGE_ROW_HEIGHT * Math.floor(VISIBLE_ROWS / 2),
    height: AGE_ROW_HEIGHT,
    borderRadius: 10,
    backgroundColor: SETUP_COLORS.panel2,
    borderWidth: 1,
    borderColor: SETUP_COLORS.accent,
  },
  content: { paddingVertical: AGE_ROW_HEIGHT * Math.floor(VISIBLE_ROWS / 2) },
  row: { height: AGE_ROW_HEIGHT, alignItems: "center", justifyContent: "center", paddingRight: 34 },
  text: { fontSize: 20, fontWeight: "600", color: SETUP_COLORS.muted, fontVariant: ["tabular-nums"] },
  textOn: { color: SETUP_COLORS.text, fontWeight: "800", fontSize: 22 },
  unitWrap: {
    position: "absolute",
    right: 16,
    top: AGE_ROW_HEIGHT * Math.floor(VISIBLE_ROWS / 2),
    height: AGE_ROW_HEIGHT,
    justifyContent: "center",
  },
  unit: { fontSize: 13, color: SETUP_COLORS.muted },
});
