import { useState } from "react";
import {
  Modal, Platform, Pressable, StyleSheet, Text, View,
} from "react-native";
import DateTimePicker, {
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker";

import { theme } from "../theme";

/** Default: one hour from now, rounded up to the next 5 minutes (matches web). */
export function defaultStartDate(): Date {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  d.setMinutes(Math.ceil(d.getMinutes() / 5) * 5, 0, 0);
  return d;
}

export function formatStartLabel(d: Date): string {
  try {
    return d.toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return d.toISOString();
  }
}

type Props = {
  value: Date;
  onChange: (next: Date) => void;
  label?: string;
};

/**
 * Friendly start-time control — tap to open the platform date/time picker
 * instead of typing an ISO string by hand.
 */
export default function StartTimeField({ value, onChange, label = "Start time" }: Props) {
  const [open, setOpen] = useState(false);
  // Android opens date then time in sequence; track which step we're on.
  const [androidStep, setAndroidStep] = useState<"date" | "time">("date");

  function commit(event: DateTimePickerEvent, date?: Date) {
    if (event.type === "dismissed") {
      setOpen(false);
      setAndroidStep("date");
      return;
    }
    if (!date) return;

    if (Platform.OS === "android") {
      if (androidStep === "date") {
        // Keep the previously chosen time-of-day; swap in the new calendar day.
        const merged = new Date(value);
        merged.setFullYear(date.getFullYear(), date.getMonth(), date.getDate());
        onChange(merged);
        setAndroidStep("time");
        return;
      }
      const merged = new Date(value);
      merged.setHours(date.getHours(), date.getMinutes(), 0, 0);
      onChange(merged);
      setOpen(false);
      setAndroidStep("date");
      return;
    }

    onChange(date);
  }

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>
      <Pressable
        onPress={() => {
          setAndroidStep("date");
          setOpen(true);
        }}
        style={({ pressed }) => [styles.field, pressed && styles.fieldPressed]}
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${formatStartLabel(value)}. Double tap to change.`}
      >
        <Text style={styles.value}>{formatStartLabel(value)}</Text>
        <Text style={styles.editHint}>Change</Text>
      </Pressable>

      {open && Platform.OS === "android" ? (
        <DateTimePicker
          value={value}
          mode={androidStep}
          display="default"
          minuteInterval={5}
          onChange={commit}
        />
      ) : null}

      {open && Platform.OS === "ios" ? (
        <Modal transparent animationType="slide" onRequestClose={() => setOpen(false)}>
          <Pressable style={styles.scrim} onPress={() => setOpen(false)} />
          <View style={styles.sheet}>
            <View style={styles.sheetHead}>
              <Text style={styles.sheetTitle}>{label}</Text>
              <Pressable onPress={() => setOpen(false)} hitSlop={10}>
                <Text style={styles.done}>Done</Text>
              </Pressable>
            </View>
            <DateTimePicker
              value={value}
              mode="datetime"
              display="spinner"
              minuteInterval={5}
              themeVariant="dark"
              onChange={commit}
              style={styles.iosPicker}
            />
          </View>
        </Modal>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 6 },
  label: { color: theme.colors.muted, fontSize: 12, fontWeight: "600" },
  field: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 10,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 12,
    backgroundColor: "rgba(0,0,0,0.2)",
  },
  fieldPressed: { opacity: 0.75 },
  value: { color: theme.colors.text, fontSize: 15, fontWeight: "600", flex: 1 },
  editHint: { color: theme.colors.accent, fontSize: 13, fontWeight: "700" },
  scrim: { flex: 1, backgroundColor: "rgba(0,0,0,0.45)" },
  sheet: {
    backgroundColor: "#160b2e",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingBottom: 28,
    paddingTop: 8,
  },
  sheetHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingBottom: 4,
  },
  sheetTitle: { color: theme.colors.text, fontSize: 16, fontWeight: "700" },
  done: { color: theme.colors.accent, fontSize: 16, fontWeight: "700" },
  iosPicker: { height: 216, alignSelf: "stretch" },
});
