import * as Notifications from "expo-notifications";
import { StatusBar } from "expo-status-bar";
import { useEffect, useRef, useState } from "react";
import {
  Animated, AppState, I18nManager, Platform, Pressable, SafeAreaView, StyleSheet, Text, View,
} from "react-native";
import { useAndroidBack, useAndroidBackTo } from "./src/hooks/useAndroidBack";

import AmbientBackground from "./src/components/AmbientBackground";
import Banner, { type BannerPayload } from "./src/components/Banner";
import BottomTabs from "./src/components/BottomTabs";
import ErrorBoundary from "./src/components/ErrorBoundary";
import SwipeTabContainer from "./src/components/SwipeTabContainer";
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
  applyVoicePrefsToTts, voicePrefsFromSettings,
} from "./src/narrationTts";
import {
  getMyList, getReadIds, getSettings, getPreviewMode, listContinue, setPreviewMode,
} from "./src/storage";
import AuthScreen, { AuthLoadingScreen, MfaAuthScreen } from "./src/screens/AuthScreen";
import { AuthProvider, useAuth } from "./src/auth/AuthContext";
import AudioCoursesScreen from "./src/screens/AudioCoursesScreen";
import CareersScreen from "./src/screens/CareersScreen";
import DriveModeScreen from "./src/screens/DriveModeScreen";
import HomeScreen from "./src/screens/HomeScreen";
import MyListScreen from "./src/screens/MyListScreen";
import NotificationsScreen from "./src/screens/NotificationsScreen";
import SettingsScreen from "./src/screens/SettingsScreen";
import BugReportScreen from "./src/screens/BugReportScreen";
import GroupClassesScreen from "./src/screens/GroupClassesScreen";
import LiveClassScreen from "./src/screens/LiveClassScreen";
import LiveRoomsScreen from "./src/screens/LiveRoomsScreen";
import LiveRoomScreen from "./src/screens/LiveRoomScreen";
import ArcadeScreen from "./src/screens/ArcadeScreen";
import GameScreen from "./src/screens/GameScreen";
import LessonScreen from "./src/screens/LessonScreen";
import RewardsScreen from "./src/screens/RewardsScreen";
import AccountScreen from "./src/screens/AccountScreen";
import SecurityScreen from "./src/screens/SecurityScreen";
import BillingScreen from "./src/screens/BillingScreen";
import LanguagesScreen from "./src/screens/LanguagesScreen";
import SearchScreen from "./src/screens/SearchScreen";
import DemoScreen from "./src/screens/DemoScreen";
import DraggableBugButton from "./src/components/DraggableBugButton";
import SignInGate from "./src/components/SignInGate";
import PrimaryButton from "./src/components/PrimaryButton";
import {
  createStudent, getFlag, getMe, getNotificationsFeed, listStudents, startSoloLiveRoom,
  type BugScreenshotUpload,
} from "./src/api";
import { installClientLog } from "./src/clientLog";
import { theme } from "./src/theme";
import type { TabId } from "./src/types";
import { setSettings } from "./src/storage";

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
  const [showLiveClass, setShowLiveClass] = useState(false);
  const [showLiveRooms, setShowLiveRooms] = useState(false);
  const [showArcade, setShowArcade] = useState(false);
  const [gameFromArcade, setGameFromArcade] = useState(false);
  const [gameTypeHint, setGameTypeHint] = useState<string | null>(null);
  const [liveRoomsOrigin, setLiveRoomsOrigin] = useState<"solo" | "group" | null>(null);
  const [liveRoomOrigin, setLiveRoomOrigin] = useState<"solo" | "group" | "liveRooms" | null>(null);
  const [liveRoomId, setLiveRoomId] = useState<string | null>(null);
  const [liveModeratorKey, setLiveModeratorKey] = useState("");
  const [gameSubject, setGameSubject] = useState<string | null>(null);
  const [showRewards, setShowRewards] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const [showSecurity, setShowSecurity] = useState(false);
  const [showBilling, setShowBilling] = useState(false);
  const [showLanguages, setShowLanguages] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [showDemo, setShowDemo] = useState(false);
  const [showBugReport, setShowBugReport] = useState(false);
  const [bugReporterEnabled, setBugReporterEnabled] = useState(true);
  const [bugCapture, setBugCapture] = useState<BugScreenshotUpload | null>(null);
  const [bugCaptureBusy, setBugCaptureBusy] = useState(false);
  const [previewMode, setPreviewModeState] = useState(false);
  const [activeLesson, setActiveLesson] = useState<
    { id: string; title: string; preview?: string; classType?: "solo" | "group" } | null
  >(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [banner, setBanner] = useState<BannerPayload | null>(null);
  const [surveyManualToken, setSurveyManualToken] = useState(0);
  const [authEpoch, setAuthEpoch] = useState(0);
  const [drivingStatus, setDrivingStatus] = useState<DrivingStatus>(getDrivingStatus());
  const authenticated = authStatus === "authenticated";
  const inApp = authenticated || previewMode;
  const captureViewRef = useRef<View>(null);

  useEffect(() => {
    installClientLog();
  }, []);

  useEffect(() => {
    let alive = true;
    const refresh = () => {
      void getFlag("engagement.in_app_bug_reporter")
        .then((value) => { if (alive) setBugReporterEnabled(value !== false); })
        .catch(() => { /* Memory unavailable: default-on keeps QA accessible. */ });
    };
    refresh();
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") refresh();
    });
    return () => { alive = false; sub.remove(); };
  }, [authEpoch]);

  useEffect(() => {
    void getPreviewMode().then(setPreviewModeState);
  }, []);

  async function enterGuestBrowse() {
    await setPreviewMode(true);
    setPreviewModeState(true);
  }

  async function exitPreviewToAuth() {
    await setPreviewMode(false);
    setPreviewModeState(false);
  }

  function requireAuth(action: () => void) {
    if (authenticated) {
      action();
      return;
    }
    void exitPreviewToAuth();
  }

  useEffect(() => {
    if (prevAuthStatusRef.current !== "authenticated" && authStatus === "authenticated") {
      setAuthEpoch((n) => n + 1);
    }
    // On sign-out (authenticated -> unauthenticated) return to a clean signed-out
    // state: reset to the home tab, close every open feature screen/modal, and
    // exit guest-preview so the app drops back to the sign-in screen instead of
    // leaving the user on Settings with access to gated features.
    if (prevAuthStatusRef.current === "authenticated" && authStatus === "unauthenticated") {
      setTab("home");
      setOpenCourseId(null);
      setShowGroupClasses(false);
      setShowLiveClass(false);
      setShowLiveRooms(false);
      setShowArcade(false);
      setGameFromArcade(false);
      setGameTypeHint(null);
      setLiveRoomsOrigin(null);
      setLiveRoomOrigin(null);
      setLiveRoomId(null);
      setLiveModeratorKey("");
      setGameSubject(null);
      setShowRewards(false);
      setShowAccount(false);
      setShowSecurity(false);
      setShowBilling(false);
      setShowLanguages(false);
      setShowSearch(false);
      setShowBugReport(false);
      setActiveLesson(null);
      setPreviewModeState(false);
      void setPreviewMode(false);
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
  }, [tab, showGroupClasses, showLiveClass, showLiveRooms, showArcade, liveRoomId, gameSubject,
    activeLesson, showRewards, showAccount, showSecurity, showBilling, showLanguages, showBugReport, fade]);

  useEffect(() => {
    if (!authenticated) return;
    const guard = { cancelled: false };
    const subs: { remove(): void }[] = [];
    void bootstrap(guard, subs);
    void syncDrivingDetection();
    return () => {
      guard.cancelled = true;
      subs.forEach(s => s.remove());
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

  async function syncStudentProfile() {
    try {
      const { students } = await listStudents();
      let id = students[0]?.id;
      if (!id) {
        const me = await getMe();
        const created = await createStudent(me.display_name || me.email.split("@")[0]);
        id = created.id;
      }
      if (id) await setSettings({ studentId: id });
    } catch {}
  }

  async function bootstrap(guard?: { cancelled: boolean }, subs?: { remove(): void }[]) {
    installNotificationHandler();
    void syncStudentProfile();
    try {
      const granted = await ensurePermissions();
      const settings = await getSettings();
      applyVoicePrefsToTts(voicePrefsFromSettings(settings));
      if (granted && settings.notificationsEnabled) {
        await rescheduleDailyReminder(settings);
      }
    } catch {}

    const handleDeepLink = (deepLink: string) => {
      if (deepLink === "aiclassroom://drive") {
        setTab("drive"); setOpenCourseId(null);
      } else if (deepLink === "aiclassroom://group" || deepLink === "aiclassroom://groupclasses") {
        setShowGroupClasses(true);
      } else if (deepLink === "aiclassroom://live" || deepLink === "aiclassroom://liverooms") {
        setShowLiveRooms(true);
      } else if (deepLink === "aiclassroom://lesson") {
        setShowLiveClass(true);
      } else if (deepLink === "aiclassroom://rewards") {
        setShowRewards(true);
      } else {
        setTab("notifications");
      }
    };

    const receivedSub = Notifications.addNotificationReceivedListener((n) => {
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
          } else if (data.deepLink) {
            handleDeepLink(data.deepLink);
          } else {
            setTab("notifications");
          }
        },
      });
    });
    subRef.current = receivedSub;
    if (guard?.cancelled) { receivedSub.remove(); subRef.current = null; } else { subs?.push(receivedSub); }

    const responseSub = Notifications.addNotificationResponseReceivedListener((resp) => {
      const data = (resp.notification.request.content.data || {}) as
        { courseId?: string; deepLink?: string };
      if (data.courseId) {
        setOpenCourseId(data.courseId); setTab("drive");
      } else if (data.deepLink) {
        handleDeepLink(data.deepLink);
      } else { setTab("notifications"); }
    });
    respRef.current = responseSub;
    if (guard?.cancelled) { responseSub.remove(); respRef.current = null; } else { subs?.push(responseSub); }

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
  const openCourse = (id: string) => {
    if (!authenticated) {
      void exitPreviewToAuth();
      return;
    }
    setOpenCourseId(id);
    setTab("drive");
  };
  const openCategory = (category: string) => {
    setBrowseCategory(category); setOpenCourseId(null); setTab("drive");
  };

  const openGame = (subject: string, fromArcade = false, gameType?: string) => {
    setGameFromArcade(fromArcade);
    setGameTypeHint(gameType || null);
    setShowArcade(false);
    setGameSubject(subject);
  };
  const openLesson = (
    id: string, title: string, preview?: string, classType: "solo" | "group" = "group",
  ) => setActiveLesson({ id, title, preview, classType });

  const onTabChange = (id: TabId) => {
    if (id === "drive" && tab === "drive") setOpenCourseId(null);
    setShowGroupClasses(false);
    setShowLiveClass(false);
    setShowLiveRooms(false);
    setShowArcade(false);
    setGameFromArcade(false);
    setGameTypeHint(null);
    setLiveRoomId(null);
    setGameSubject(null);
    setActiveLesson(null);
    setShowRewards(false);
    setShowAccount(false);
    setShowSecurity(false);
    setShowBilling(false);
    setShowLanguages(false);
    setShowSearch(false);
    setShowBugReport(false);
    void refreshUnreadAndAlerts();
    setTab(id);
  };

  const bugContext = liveRoomId
    ? `live-room:${liveRoomId}`
    : activeLesson
      ? `lesson:${activeLesson.id}`
      : openCourseId
        ? `course:${openCourseId}`
        : showGroupClasses
          ? "group-classes"
          : showLiveClass
            ? "live-class"
            : showLiveRooms
              ? "live-rooms"
              : showArcade
                ? "arcade"
                : gameSubject
                  ? `game:${gameSubject}`
                  : `tab:${tab}`;

  async function openBugReporter() {
    if (bugCaptureBusy) return;
    setBugCaptureBusy(true);
    let screenshot: BugScreenshotUpload | null = null;
    try {
      if (Platform.OS !== "web") {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const { captureRef } = require("react-native-view-shot") as typeof import("react-native-view-shot");
        const dataUri = await captureRef(captureViewRef, {
          format: "jpg",
          quality: 0.5,
          result: "data-uri",
          handleGLSurfaceViewOnAndroid: true,
        });
        const dataBase64 = dataUri.split(",", 2)[1] || "";
        // Drop oversized captures so /memory/bugs does not fail mid-upload.
        const approxBytes = Math.floor((dataBase64.replace(/=+$/, "").length * 3) / 4);
        if (dataBase64 && approxBytes <= 1_500_000) {
          screenshot = {
            filename: "app-screen.jpg",
            content_type: "image/jpeg",
            data_base64: dataBase64,
          };
        }
      }
    } catch {
      // Some native surfaces (camera/video) cannot be snapshotted. The report
      // still opens with logs, API traces, stack, and contextual metadata.
    } finally {
      setBugCapture(screenshot);
      setShowBugReport(true);
      setBugCaptureBusy(false);
    }
  }

  const mainTabsVisible = !liveRoomId && !showGroupClasses && !showLiveClass
    && !showLiveRooms && !showArcade && !gameSubject && !activeLesson
    && !showRewards && !showAccount && !showSecurity && !showBilling && !showLanguages
    && !showSearch && !showBugReport;

  // Android hardware / gesture back: when no overlay screen owns the handler,
  // pop to Home from secondary tabs (standard Android tab UX). On Home, allow
  // the default activity exit. Overlay screens wire this via useAndroidBackTo.
  useAndroidBack(
    () => {
      if (tab !== "home") {
        onTabChange("home");
        return true;
      }
      return false;
    },
    inApp && mainTabsVisible && !openCourseId,
  );

  let screen: React.ReactNode = null;
  if (showBugReport) {
    screen = (
      <BugReportScreen
        screen={bugContext}
        initialScreenshot={bugCapture}
        onBack={() => { setShowBugReport(false); setBugCapture(null); }}
      />
    );
  } else if (showBilling) {
    screen = <BillingScreen onBack={() => setShowBilling(false)} />;
  } else if (showSecurity) {
    screen = <SecurityScreen onBack={() => setShowSecurity(false)} />;
  } else if (showAccount) {
    screen = (
      <AccountScreen
        onBack={() => setShowAccount(false)}
        onOpenSecurity={() => { setShowAccount(false); setShowSecurity(true); }}
        onOpenBilling={() => { setShowAccount(false); setShowBilling(true); }}
      />
    );
  } else if (showRewards) {
    screen = <RewardsScreen onBack={() => setShowRewards(false)} />;
  } else if (showLanguages) {
    screen = <LanguagesScreen onBack={() => setShowLanguages(false)} />;
  } else if (showSearch) {
    screen = (
      <SearchScreen
        onBack={() => setShowSearch(false)}
        onOpenCourse={(id) => { setShowSearch(false); openCourse(id); }}
        onOpenSettings={(section) => {
          setShowSearch(false);
          if (section === "account") {
            requireAuth(() => setShowAccount(true));
          } else {
            setTab("settings");
          }
        }}
      />
    );
  } else if (gameSubject) {
    screen = (
      <GameScreen
        subject={gameSubject}
        initialGameType={gameTypeHint || undefined}
        onBack={() => {
          setGameSubject(null);
          setGameTypeHint(null);
          if (gameFromArcade) {
            setShowArcade(true);
            setGameFromArcade(false);
          }
        }}
      />
    );
  } else if (showArcade) {
    screen = (
      <ArcadeScreen
        onOpenSubject={(subject, gameType) => openGame(subject, true, gameType)}
        onBack={() => setShowArcade(false)}
      />
    );
  } else if (activeLesson) {
    screen = (
      <LessonScreen
        lessonId={activeLesson.id}
        title={activeLesson.title}
        preview={activeLesson.preview}
        classType={activeLesson.classType}
        onBack={() => setActiveLesson(null)}
      />
    );
  } else if (liveRoomId) {
    screen = (
      <LiveRoomScreen
        roomId={liveRoomId}
        moderatorKey={liveModeratorKey}
        onBack={() => {
          setLiveRoomId(null);
          setLiveModeratorKey("");
          if (liveRoomOrigin === "solo") setShowLiveClass(true);
          else if (liveRoomOrigin === "liveRooms") setShowLiveRooms(true);
          else setShowGroupClasses(true);
          setLiveRoomOrigin(null);
        }}
      />
    );
  } else if (showLiveRooms) {
    screen = (
      <LiveRoomsScreen
        onOpenRoom={(id, modKey) => {
          setLiveRoomId(id);
          setLiveModeratorKey(modKey || "");
          setShowLiveRooms(false);
          setLiveRoomOrigin("liveRooms");
        }}
        onBack={() => {
          setShowLiveRooms(false);
          if (liveRoomsOrigin === "solo") setShowLiveClass(true);
          if (liveRoomsOrigin === "group") setShowGroupClasses(true);
          setLiveRoomsOrigin(null);
        }}
      />
    );
  } else if (showLiveClass) {
    screen = (
      <LiveClassScreen
        onStart={async (id, title, classType) => {
          // Solo 1:1 opens the SAME Salareen live room as group classes (video
          // tiles, chat, Q&A, narration), just sized for the AI host + you.
          if (classType === "solo") {
            try {
              const { room_id } = await startSoloLiveRoom(id);
              setLiveModeratorKey("");
              setShowLiveClass(false);
              setLiveRoomOrigin("solo");
              setLiveRoomId(room_id);
              return;
            } catch {
              // Room couldn't open (offline) — fall back to the lesson presenter.
            }
          }
          setShowLiveClass(false);
          setActiveLesson({ id, title, classType });
        }}
        onOpenLiveRooms={() => {
          setShowLiveClass(false);
          setLiveRoomsOrigin("solo");
          setShowLiveRooms(true);
        }}
        onOpenGroupClasses={() => {
          setShowLiveClass(false);
          setShowGroupClasses(true);
        }}
        onBack={() => setShowLiveClass(false)}
      />
    );
  } else if (showGroupClasses) {
    screen = (
      <GroupClassesScreen
        onOpenRoom={(id, modKey) => {
          setLiveRoomId(id);
          setLiveModeratorKey(modKey || "");
          setShowGroupClasses(false);
          setLiveRoomOrigin("group");
        }}
        onOpenLiveRooms={() => {
          setShowGroupClasses(false);
          setLiveRoomsOrigin("group");
          setShowLiveRooms(true);
        }}
        onBack={() => setShowGroupClasses(false)}
      />
    );
  } else if (tab === "home") {
    screen = (
      <HomeScreen
        onOpenCourse={openCourse}
        onOpenCategory={openCategory}
        onOpenArcade={() => setShowArcade(true)}
        onOpenGroupClasses={() => setShowGroupClasses(true)}
        onOpenLiveClass={() => setShowLiveClass(true)}
        onOpenLanguages={() => requireAuth(() => setShowLanguages(true))}
        onOpenRewards={() => requireAuth(() => setShowRewards(true))}
        onOpenSearch={() => setShowSearch(true)}
        guestMode={!authenticated}
      />
    );
  } else if (tab === "drive") {
    screen = openCourseId
      ? (
        !authenticated ? (
          <GuestFeatureGate
            onBack={() => setOpenCourseId(null)}
            onSignIn={() => void exitPreviewToAuth()}
          />
        ) : (
          <DriveModeScreen
            courseId={openCourseId}
            isDriving={drivingStatus.phase === "driving"}
            onBack={() => setOpenCourseId(null)}
          />
        )
      )
      : (
        <AudioCoursesScreen
          onOpen={openCourse}
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
        guestMode={!authenticated}
        onOpenAccount={() => requireAuth(() => setShowAccount(true))}
        onOpenRewards={() => requireAuth(() => setShowRewards(true))}
        onOpenLanguages={() => requireAuth(() => setShowLanguages(true))}
        onOpenBilling={() => requireAuth(() => setShowBilling(true))}
        onOpenBugReport={bugReporterEnabled ? () => void openBugReporter() : undefined}
        onSignIn={() => void exitPreviewToAuth()}
      />
    );
  }

  // React-Native-Web honors writingDirection on the root so RTL locales (ar,
  // he, ur, fa) lay out from right to left without a force-reload. On native,
  // I18nManager.forceRTL would require a relaunch, which is annoying for
  // demos - we keep the in-app layout pragmatic and let native users restart.
  void I18nManager;

  const floatingBugButton = bugReporterEnabled && !showBugReport ? (
    <DraggableBugButton
      onPress={() => void openBugReporter()}
      disabled={bugCaptureBusy}
      aboveTabs={inApp && mainTabsVisible}
    />
  ) : null;

  if (authStatus === "loading" && !showBugReport) {
    return (
      <SafeAreaView ref={captureViewRef} collapsable={false} style={styles.root}>
        <StatusBar style="light" />
        <AmbientBackground />
        <AuthLoadingScreen />
        {floatingBugButton}
      </SafeAreaView>
    );
  }

  if (authStatus === "mfa_pending" && !showBugReport) {
    return (
      <SafeAreaView ref={captureViewRef} collapsable={false} style={styles.root}>
        <StatusBar style="light" />
        <AmbientBackground />
        <MfaAuthScreen />
        {floatingBugButton}
      </SafeAreaView>
    );
  }

  if (showDemo && !showBugReport) {
    return (
      <SafeAreaView ref={captureViewRef} collapsable={false} style={styles.root}>
        <StatusBar style="light" />
        <AmbientBackground />
        <DemoScreen
          onSelectCourse={async (courseId, title) => {
            await enterGuestBrowse();
            setShowDemo(false);
            setOpenCourseId(courseId);
            setTab("drive");
          }}
          onOpenFeature={async (featureId) => {
            await enterGuestBrowse();
            setShowDemo(false);
            if (featureId === "drive") setTab("drive");
            else if (featureId === "arcade") setShowArcade(true);
            else if (featureId === "languages") setShowLanguages(true);
            else if (featureId === "solo") setShowLiveClass(true);
            else setTab("home");
          }}
          onEnterFullApp={async () => {
            await enterGuestBrowse();
            setShowDemo(false);
          }}
        />
        {floatingBugButton}
      </SafeAreaView>
    );
  }

  if (!inApp && !showBugReport) {
    return (
      <SafeAreaView ref={captureViewRef} collapsable={false} style={styles.root}>
        <StatusBar style="light" />
        <AmbientBackground />
        <AuthScreen onBrowseGuest={() => void enterGuestBrowse()} />
        <Pressable
          onPress={() => setShowDemo(true)}
          style={styles.demoBtn}
          accessibilityRole="button"
          accessibilityLabel="Sales demo mode"
        >
          <Text style={styles.demoBtnText}>✨ Sales Demo</Text>
        </Pressable>
        {floatingBugButton}
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView ref={captureViewRef} collapsable={false} style={styles.root}>
      <StatusBar style="light" />
      <AmbientBackground />
      <View style={[{ flex: 1 }, isRTL && { direction: "rtl" }]}>
        <Banner banner={banner} onDismiss={() => setBanner(null)} />
        <Animated.View style={{ flex: 1, opacity: fade }}>
          <SwipeTabContainer
            active={tab}
            enabled={mainTabsVisible && !openCourseId}
            onChange={onTabChange}
          >
            <ErrorBoundary
              resetKey={`${tab}:${liveRoomId ?? ""}:${activeLesson?.id ?? ""}:${openCourseId ?? ""}`}
              onReset={() => onTabChange("home")}
            >
              {screen}
            </ErrorBoundary>
          </SwipeTabContainer>
        </Animated.View>
        <LearningProfileSurvey
          authEpoch={authEpoch}
          manualOpenToken={surveyManualToken}
        />
      </View>
      {inApp && mainTabsVisible ? (
        <BottomTabs
          active={tab}
          onChange={onTabChange}
          unreadCount={unreadCount}
        />
      ) : null}
      {floatingBugButton}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: theme.colors.bg },
  demoBtn: {
    position: "absolute",
    bottom: 32,
    alignSelf: "center",
    backgroundColor: "rgba(99,102,241,0.18)",
    borderWidth: 1,
    borderColor: "rgba(99,102,241,0.45)",
    borderRadius: 24,
    paddingHorizontal: 24,
    paddingVertical: 10,
  },
  demoBtnText: { color: "#a5b4fc", fontSize: 14, fontWeight: "700", letterSpacing: 0.5 },
});

function GuestFeatureGate({
  onBack, onSignIn,
}: {
  onBack: () => void;
  onSignIn: () => void;
}) {
  const { t } = useT();
  useAndroidBackTo(onBack);
  return (
    <View style={{ flex: 1, paddingTop: 56, paddingHorizontal: theme.spacing.screenX }}>
      <PrimaryButton label={t("drive.back")} onPress={onBack} variant="ghost" />
      <SignInGate
        title={t("preview.lockedTitle")}
        body={t("preview.lockedBody")}
        signInLabel={t("preview.signIn")}
        onSignIn={onSignIn}
      />
    </View>
  );
}
