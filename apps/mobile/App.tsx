import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";
import { useEffect, useRef, useState } from "react";
import { Animated, I18nManager, SafeAreaView, StyleSheet, View } from "react-native";

import AmbientBackground from "./src/components/AmbientBackground";
import Banner, { type BannerPayload } from "./src/components/Banner";
import BottomTabs from "./src/components/BottomTabs";
import { LocaleProvider, useT } from "./src/i18n";
import LearningProfileSurvey from "./src/components/LearningProfileSurvey";
import {
  ensurePermissions, fireDrivingDetectedAlert, installNotificationHandler,
  rescheduleDailyReminder, scheduleAlertsFor,
} from "./src/notifications";
import {
  getDrivingStatus, startDrivingDetection, stopDrivingDetection,
  subscribeDrivingStatus, type DrivingPhase, type DrivingStatus,
} from "./src/drivingDetection";
import {
  getMyList, getReadIds, getSettings, listContinue, loadAuthToken,
} from "./src/storage";
import AudioCoursesScreen from "./src/screens/AudioCoursesScreen";
import DriveModeScreen from "./src/screens/DriveModeScreen";
import HomeScreen from "./src/screens/HomeScreen";
import MyListScreen from "./src/screens/MyListScreen";
import NotificationsScreen from "./src/screens/NotificationsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import CareersScreen from "./src/screens/CareersScreen";
import { getNotificationsFeed } from "./src/api";
import { theme } from "./src/theme";
import type { TabId } from "./src/types";

export default function App() {
  return (
    <LocaleProvider>
      <AppInner />
    </LocaleProvider>
  );
}

function AppInner() {
  const { t, isRTL } = useT();
  const [tab, setTab] = useState<TabId>("home");
  const [browseCategory, setBrowseCategory] = useState<string>("");
  const [openCourseId, setOpenCourseId] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [banner, setBanner] = useState<BannerPayload | null>(null);
  const [surveyManualToken, setSurveyManualToken] = useState(0);
  const [authEpoch, setAuthEpoch] = useState(0);
  const [showCareers, setShowCareers] = useState(false);
  const [drivingStatus, setDrivingStatus] = useState<DrivingStatus>(getDrivingStatus());

  const subRef = useRef<Notifications.Subscription | null>(null);
  const respRef = useRef<Notifications.Subscription | null>(null);
  const fade = useRef(new Animated.Value(1)).current;
  const prevDrivingPhaseRef = useRef<DrivingPhase>("unknown");

  useEffect(() => {
    fade.setValue(0);
    Animated.timing(fade, {
      toValue: 1,
      duration: theme.motion.fadeDuration,
      useNativeDriver: true,
    }).start();
  }, [tab, showCareers, fade]);

  useEffect(() => {
    void bootstrap();
    void syncDrivingDetection();
    return () => {
      subRef.current?.remove();
      respRef.current?.remove();
      void stopDrivingDetection();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => subscribeDrivingStatus(setDrivingStatus), []);

  async function syncDrivingDetection() {
    const settings = await getSettings();
    await startDrivingDetection(settings);
  }

  useEffect(() => {
    const prev = prevDrivingPhaseRef.current;
    prevDrivingPhaseRef.current = drivingStatus.phase;
    if (drivingStatus.phase !== "driving" || prev === "driving") return;

    void (async () => {
      const settings = await getSettings();
      const cont = await listContinue();
      const courseId = cont[0]?.id;

      if (settings.driveDrivingAlerts && settings.notificationsEnabled) {
        await fireDrivingDetectedAlert(courseId);
      }

      setBanner({
        kind: "live",
        title: t("driving.bannerTitle"),
        body: t("driving.bannerBody"),
        cta: t("banner.open"),
        ttlMs: 8000,
        onPress: () => {
          if (courseId) {
            setOpenCourseId(courseId);
            setTab("drive");
          } else {
            setTab("drive");
          }
        },
      });

      if (settings.driveAutoLaunch) {
        if (courseId) {
          setOpenCourseId(courseId);
          setTab("drive");
        } else {
          setTab("drive");
        }
      }
    })();
  }, [drivingStatus.phase, t]);

  async function bootstrap() {
    installNotificationHandler();
    await loadAuthToken();
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
        body: c.body || undefined, cta: t("banner.open"),
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
      } else if (data.deepLink === "aiclassroom://drive") {
        setTab("drive"); setOpenCourseId(null);
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
  if (showCareers) {
    screen = (
      <CareersScreen
        onBack={() => setShowCareers(false)}
        onOpenCourse={(id) => { setShowCareers(false); openCourse(id); }}
      />
    );
  } else if (tab === "home") {
    screen = (
      <HomeScreen
        onOpenCourse={openCourse}
        onOpenCategory={openCategory}
        onOpenCareers={() => setShowCareers(true)}
      />
    );
  } else if (tab === "drive") {
    screen = openCourseId
      ? (
        <DriveModeScreen
          courseId={openCourseId}
          isDriving={drivingStatus.phase === "driving"}
          onBack={() => setOpenCourseId(null)}
        />
      )
      : <AudioCoursesScreen onOpen={openCourse} initialCategory={browseCategory} />;
  } else if (tab === "mylist") {
    screen = <MyListScreen onOpenCourse={openCourse} />;
  } else if (tab === "notifications") {
    screen = <NotificationsScreen onOpenCourse={openCourse} onUnreadChange={setUnreadCount} />;
  } else if (tab === "settings") {
    screen = (
      <SettingsScreen
        onAuthChange={() => setAuthEpoch((n) => n + 1)}
        onOpenLearningProfile={() => setSurveyManualToken((n) => n + 1)}
        drivingStatus={drivingStatus}
        onDrivingSettingsChange={() => void syncDrivingDetection()}
      />
    );
  }

  // React-Native-Web honors writingDirection on the root so RTL locales (ar,
  // he, ur, fa) lay out from right to left without a force-reload. On native,
  // I18nManager.forceRTL would require a relaunch, which is annoying for
  // demos - we keep the in-app layout pragmatic and let native users restart.
  void I18nManager;
  return (
    <SafeAreaView style={styles.root}>
      <StatusBar style="light" />
      <AmbientBackground />
      <View style={[{ flex: 1 }, isRTL && { direction: "rtl" }]}>
        <Banner banner={banner} onDismiss={() => setBanner(null)} />
        <Animated.View style={{ flex: 1, opacity: fade }}>
          {screen}
        </Animated.View>
        <LearningProfileSurvey
          key={authEpoch}
          manualOpenToken={surveyManualToken}
          onSaved={() => setAuthEpoch((n) => n + 1)}
        />
      </View>
      {!showCareers ? (
        <BottomTabs
          active={tab}
          onChange={(id) => {
            if (id === "drive" && tab === "drive") setOpenCourseId(null);
            void refreshUnreadAndAlerts();
            setTab(id);
          }}
          unreadCount={unreadCount}
        />
      ) : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.bg },
});
