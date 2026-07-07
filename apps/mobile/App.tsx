import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";
import { useEffect, useRef, useState } from "react";
import { Animated, I18nManager, SafeAreaView, StyleSheet, View } from "react-native";

import AmbientBackground from "./src/components/AmbientBackground";
import Banner, { type BannerPayload } from "./src/components/Banner";
import BottomTabs from "./src/components/BottomTabs";
import { LocaleProvider, useT } from "./src/i18n";
import { IntroSplashProvider } from "./src/introSplash";
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
  getMyList, getReadIds, getSettings, listContinue,
} from "./src/storage";
import AuthScreen, { AuthLoadingScreen } from "./src/screens/AuthScreen";
import { AuthProvider, useAuth } from "./src/auth/AuthContext";
import AudioCoursesScreen from "./src/screens/AudioCoursesScreen";
import CareersScreen from "./src/screens/CareersScreen";
import DriveModeScreen from "./src/screens/DriveModeScreen";
import HomeScreen from "./src/screens/HomeScreen";
import MyListScreen from "./src/screens/MyListScreen";
import NotificationsScreen from "./src/screens/NotificationsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import GroupClassesScreen from "./src/screens/GroupClassesScreen";
import LiveRoomScreen from "./src/screens/LiveRoomScreen";
import GameScreen from "./src/screens/GameScreen";
import LessonScreen from "./src/screens/LessonScreen";
import { getNotificationsFeed } from "./src/api";
import { theme } from "./src/theme";
import type { TabId } from "./src/types";

export default function App() {
  return (
    <LocaleProvider>
      <IntroSplashProvider>
        <AuthProvider>
          <AppInner />
        </AuthProvider>
      </IntroSplashProvider>
    </LocaleProvider>
  );
}

function AppInner() {
  const { status: authStatus } = useAuth();
  const prevAuthStatusRef = useRef(authStatus);
  const { t, locale, isRTL } = useT();
  const [tab, setTab] = useState<TabId>("home");
  const [browseCategory, setBrowseCategory] = useState<string>("");
  const [openCourseId, setOpenCourseId] = useState<string | null>(null);
  const [showGroupClasses, setShowGroupClasses] = useState(false);
  const [liveRoomId, setLiveRoomId] = useState<string | null>(null);
  const [liveModeratorKey, setLiveModeratorKey] = useState("");
  const [gameSubject, setGameSubject] = useState<string | null>(null);
  const [activeLesson, setActiveLesson] = useState<
    { id: string; title: string; preview?: string } | null
  >(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [banner, setBanner] = useState<BannerPayload | null>(null);
  const [surveyManualToken, setSurveyManualToken] = useState(0);
  const [authEpoch, setAuthEpoch] = useState(0);
  const [drivingStatus, setDrivingStatus] = useState<DrivingStatus>(getDrivingStatus());
  const authenticated = authStatus === "authenticated";

  useEffect(() => {
    if (prevAuthStatusRef.current !== "authenticated" && authStatus === "authenticated") {
      setAuthEpoch((n) => n + 1);
    }
    prevAuthStatusRef.current = authStatus;
  }, [authStatus]);

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
  }, [tab, showGroupClasses, liveRoomId, gameSubject, activeLesson, fade]);

  useEffect(() => {
    if (!authenticated) return;
    void bootstrap();
    void syncDrivingDetection();
    return () => {
      subRef.current?.remove();
      respRef.current?.remove();
      void stopDrivingDetection();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authenticated]);

  useEffect(() => {
    if (!authenticated) return;
    return subscribeDrivingStatus(setDrivingStatus);
  }, [authenticated]);

  async function syncDrivingDetection() {
    const settings = await getSettings();
    await startDrivingDetection(settings);
  }

  useEffect(() => {
    if (!authenticated) return;
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
  }, [drivingStatus.phase, t, authenticated]);

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
        locale,
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

  const openGame = (subject: string) => setGameSubject(subject);
  const openLesson = (id: string, title: string, preview?: string) =>
    setActiveLesson({ id, title, preview });

  let screen: React.ReactNode = null;
  if (gameSubject) {
    screen = (
      <GameScreen subject={gameSubject} onBack={() => setGameSubject(null)} />
    );
  } else if (activeLesson) {
    screen = (
      <LessonScreen
        lessonId={activeLesson.id}
        title={activeLesson.title}
        preview={activeLesson.preview}
        onBack={() => setActiveLesson(null)}
      />
    );
  } else if (liveRoomId) {
    screen = (
      <LiveRoomScreen
        roomId={liveRoomId}
        moderatorKey={liveModeratorKey}
        onBack={() => { setLiveRoomId(null); setShowGroupClasses(true); setLiveModeratorKey(""); }}
      />
    );
  } else if (showGroupClasses) {
    screen = (
      <GroupClassesScreen
        onOpenRoom={(id, modKey) => {
          setLiveRoomId(id);
          setLiveModeratorKey(modKey || "");
          setShowGroupClasses(false);
        }}
        onBack={() => setShowGroupClasses(false)}
      />
    );
  } else if (tab === "home") {
    screen = (
      <HomeScreen
        onOpenCourse={openCourse}
        onOpenCategory={openCategory}
        onOpenCareers={() => setTab("careers")}
        onOpenGroupClasses={() => setShowGroupClasses(true)}
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
      : (
        <AudioCoursesScreen
          onOpen={openCourse}
          onOpenGame={openGame}
          onOpenLesson={openLesson}
          initialCategory={browseCategory}
        />
      );
  } else if (tab === "mylist") {
    screen = <MyListScreen onOpenCourse={openCourse} />;
  } else if (tab === "careers") {
    screen = (
      <CareersScreen
        onOpenCourse={openCourse}
      />
    );
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

  if (authStatus === "loading") {
    return (
      <SafeAreaView style={styles.root}>
        <StatusBar style="light" />
        <AmbientBackground />
        <AuthLoadingScreen />
      </SafeAreaView>
    );
  }

  if (authStatus === "unauthenticated") {
    return (
      <SafeAreaView style={styles.root}>
        <StatusBar style="light" />
        <AmbientBackground />
        <AuthScreen />
      </SafeAreaView>
    );
  }

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
          authEpoch={authEpoch}
          manualOpenToken={surveyManualToken}
        />
      </View>
      {!liveRoomId && !showGroupClasses && !gameSubject && !activeLesson ? (
        <BottomTabs
          active={tab}
          onChange={(id) => {
            if (id === "drive" && tab === "drive") setOpenCourseId(null);
            setShowGroupClasses(false);
            setLiveRoomId(null);
            setGameSubject(null);
            setActiveLesson(null);
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
