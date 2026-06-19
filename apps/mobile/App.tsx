import { StatusBar } from "expo-status-bar";
import { useState } from "react";
import AudioCoursesScreen from "./src/screens/AudioCoursesScreen";
import DriveModeScreen from "./src/screens/DriveModeScreen";

// Minimal navigation without a router dependency: this is the starting point for
// the AI Classroom mobile app (Android + iOS via Expo). It opens straight into
// Drive Mode (audio classes), which is the on-the-go learning experience.
export default function App() {
  const [courseId, setCourseId] = useState<string | null>(null);
  return (
    <>
      <StatusBar style="light" />
      {courseId
        ? <DriveModeScreen courseId={courseId} onBack={() => setCourseId(null)} />
        : <AudioCoursesScreen onOpen={setCourseId} />}
    </>
  );
}
