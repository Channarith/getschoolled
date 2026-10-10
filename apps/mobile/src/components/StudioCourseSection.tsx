import { useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import AnimatedPressable from "./AnimatedPressable";
import { STUDIO_COURSES, type StudioCourseId } from "../studioCourses";
import { theme } from "../theme";

type Props = {
  onOpen: (courseId: StudioCourseId) => void;
  presentation?: "audio";
};

/** Driver's ed and Food Health & Safety, the xAI studio courses. */
export default function StudioCourseSection({ onOpen, presentation }: Props) {
  const [busy, setBusy] = useState("");

  return (
    <View style={styles.wrap}>
      <Text style={styles.kicker}>Full courses · xAI</Text>
      <Text style={styles.lead}>
        Theodore teaches Driver's Education and Food Health & Safety with xAI.
        {presentation === "audio" ? " This opens the audio class." : " Admins take the full course. Everyone else pays."}
      </Text>
      {STUDIO_COURSES.map((course) => (
        <AnimatedPressable
          key={course.id}
          testID={`studio-course-${course.id}`}
          onPress={() => {
            setBusy(course.id);
            onOpen(course.id);
            setBusy("");
          }}
          style={styles.card}
        >
          <Text style={styles.emoji}>{course.emoji}</Text>
          <View style={styles.copy}>
            <Text style={styles.title}>{course.title}</Text>
            <Text style={styles.blurb}>{course.blurb}</Text>
          </View>
          {busy === course.id ? (
            <ActivityIndicator color={theme.colors.accent} />
          ) : (
            <Text style={styles.open}>Open</Text>
          )}
        </AnimatedPressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: theme.spacing.screenX, paddingBottom: 8, gap: 8 },
  kicker: {
    color: theme.colors.muted,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  lead: { color: theme.colors.muted, fontSize: 13, lineHeight: 18 },
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: "rgba(255,255,255,0.05)",
    padding: 12,
  },
  emoji: { fontSize: 28, flexShrink: 0 },
  copy: { flex: 1, minWidth: 0 },
  title: { color: theme.colors.text, fontSize: 16, fontWeight: "700", lineHeight: 21 },
  blurb: { color: theme.colors.muted, fontSize: 12, lineHeight: 16, marginTop: 2 },
  open: { color: "#bbf7d0", fontSize: 13, fontWeight: "700", flexShrink: 0 },
});
