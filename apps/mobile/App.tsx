import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";
import { useEffect, useRef, useState } from "react";
import { SafeAreaView, StyleSheet, View } from "react-native";

import Banner, { type BannerPayload } from "./src/components/Banner";
import BottomTabs from "./src/components/BottomTabs";
import {
  ensurePermissions, installNotificationHandler,
  rescheduleDailyReminder, scheduleAlertsFor,
} from "./src/notifications";
import {
  getMyList, getReadIds, getSettings, listContinue,
} from "./src/storage";
import AudioCoursesScreen from "./src/screens/AudioCoursesScreen";
import DriveModeScreen from "./src/screens/DriveModeScreen";
import HomeScreen from "./src/screens/HomeScreen";
import MyListScreen from "./src/screens/MyListScreen";
import NotificationsScreen from "./src/screens/NotificationsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import { getNotificationsFeed } from "./src/api";
import type { TabId } from "./src/types";

export default function App() {
  const [tab, setTab] = useState<TabId>("home");
  const [browseCategory, setBrowseCategory] = useState<string>("");
  const [openCourseId, setOpenCourseId] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [banner, setBanner] = useState<BannerPayload | null>(null);

  const subRef = useRef<Notifications.Subscription | null>(null);
  const respRef = useRef<Notifications.Subscription | null>(null);

  useEffect(() => {
    void bootstrap();
    return () => { subRef.current?.remove(); respRef.current?.remove(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function bootstrap() {
    installNotificationHandler();
    try {
      const granted = await ensurePermissions();
      const settings = await getSettings();
      if (granted && settings.notificationsEnabled) {
        await rescheduleDailyReminder(settings);
      }
    } catch {}

    subRef.current = Notifications.addNotificationReceivedListener((n) => {
      const c = n.request.content;
      setBanner({
        kind: "live", title: c.title || "AI Classroom",
        body: c.body || undefined, cta: "Open",
        ttlMs: 6000,
        onPress: () => {
          const data = (c.data || {}) as { courseId?: string; deepLink?: string };
          if (data.courseId) {
            setOpenCourseId(data.courseId);
            setTab("drive");
          } else if (data.deepLink === "aiclassroom://drive") {
            setTab("drive"); setOpenCourseId(null);
          } else {
            setTab("notifications");
          }
        },
      });
    });
    respRef.current = Notifications.addNotificationResponseReceivedListener((resp) => {
      const data = (resp.notification.request.content.data || {}) as
        { courseId?: string; deepLink?: string };
      if (data.courseId) {
        setOpenCourseId(data.courseId); setTab("drive");
      } else { setTab("notifications"); }
    });

    void refreshUnreadAndAlerts();
  }

  async function refreshUnreadAndAlerts() {
    try {
      const [interests, inProgress, completed, settings, read] = await Promise.all([
        // recordInterest is only category-scoped; we don't ship it as the
        // full interests vector. The home screen records categories the user
        // opens which serves as our interest signal.
        Promise.resolve<string[]>([]),
        listContinue(), getMyList(), getSettings(), getReadIds(),
      ]);
      const feed = await getNotificationsFeed({
        studentId: settings.studentId,
        interests, inProgress: inProgress.map((c) => c.id),
        completed,
      });
      const readSet = new Set(read);
      setUnreadCount(feed.items.filter((i) => !readSet.has(i.id)).length);
      try { await scheduleAlertsFor(feed.items, settings); } catch {}
    } catch {}
  }

  // The Drive tab opens straight into the player when a courseId is set;
  // otherwise it falls back to the audio-courses browser.
  const openCourse = (id: string) => { setOpenCourseId(id); setTab("drive"); };
  const openCategory = (category: string) => {
    setBrowseCategory(category); setOpenCourseId(null); setTab("drive");
  };

  let screen: React.ReactNode = null;
  if (tab === "home") {
    screen = <HomeScreen onOpenCourse={openCourse} onOpenCategory={openCategory} />;
  } else if (tab === "drive") {
    screen = openCourseId
      ? <DriveModeScreen courseId={openCourseId} onBack={() => setOpenCourseId(null)} />
      : <AudioCoursesScreen onOpen={openCourse} initialCategory={browseCategory} />;
  } else if (tab === "mylist") {
    screen = <MyListScreen onOpenCourse={openCourse} />;
  } else if (tab === "notifications") {
    screen = <NotificationsScreen onOpenCourse={openCourse} onUnreadChange={setUnreadCount} />;
  } else if (tab === "settings") {
    screen = <SettingsScreen />;
  }

  return (
    <SafeAreaView style={styles.root}>
      <StatusBar style="light" />
      <View style={{ flex: 1 }}>
        <Banner banner={banner} onDismiss={() => setBanner(null)} />
        {screen}
      </View>
      <BottomTabs
        active={tab}
        onChange={(id) => {
          if (id === "drive" && tab === "drive") setOpenCourseId(null);
          // Refresh unread on every tab change so the badge always reflects
          // the latest read-state - including after the user hits
          // "Mark all as read" inside the inbox.
          void refreshUnreadAndAlerts();
          setTab(id);
        }}
        unreadCount={unreadCount}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0b1020" },
});
