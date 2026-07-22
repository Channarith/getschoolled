import { useEffect, useRef } from "react";
import {
  Animated, Dimensions, Pressable, ScrollView, StyleSheet, Text, View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import Svg, { Circle, Path } from "react-native-svg";

import {
  DEMO_COURSES, DEMO_FEATURES, SALES_DEMO_FLAGS, type DemoCourse,
} from "../demo";
import { theme } from "../theme";

const { width: W } = Dimensions.get("window");
const CARD_W = W * 0.72;

function useFadeSlideIn(delay: number) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(40)).current;
  useEffect(() => {
    Animated.parallel([
      Animated.timing(opacity, { toValue: 1, duration: 500, delay, useNativeDriver: true }),
      Animated.spring(translateY, { toValue: 0, delay, useNativeDriver: true, tension: 60, friction: 8 }),
    ]).start();
  }, []);
  return { opacity, translateY };
}

function PulseRing() {
  const scale = useRef(new Animated.Value(1)).current;
  const opacity = useRef(new Animated.Value(0.6)).current;
  useEffect(() => {
    Animated.loop(
      Animated.parallel([
        Animated.sequence([
          Animated.timing(scale, { toValue: 1.35, duration: 1000, useNativeDriver: true }),
          Animated.timing(scale, { toValue: 1, duration: 1000, useNativeDriver: true }),
        ]),
        Animated.sequence([
          Animated.timing(opacity, { toValue: 0, duration: 1000, useNativeDriver: true }),
          Animated.timing(opacity, { toValue: 0.6, duration: 1000, useNativeDriver: true }),
        ]),
      ])
    ).start();
  }, []);
  return (
    <Animated.View style={{
      position: "absolute", borderRadius: 50, width: 100, height: 100,
      borderWidth: 2, borderColor: "#6366f1",
      transform: [{ scale }], opacity,
    }} />
  );
}

function CourseCard({ course, index, onPress }: { course: DemoCourse; index: number; onPress: () => void }) {
  const { opacity, translateY } = useFadeSlideIn(150 + index * 80);
  const pressScale = useRef(new Animated.Value(1)).current;
  const handlePressIn = () => Animated.spring(pressScale, { toValue: 0.96, useNativeDriver: true, tension: 200 }).start();
  const handlePressOut = () => Animated.spring(pressScale, { toValue: 1, useNativeDriver: true, tension: 200 }).start();
  return (
    <Animated.View style={[{ width: CARD_W, marginRight: 14 }, { opacity, transform: [{ translateY }, { scale: pressScale }] }]}>
      <Pressable onPress={onPress} onPressIn={handlePressIn} onPressOut={handlePressOut}>
        <LinearGradient
          colors={[course.gradientStart, course.gradientEnd]}
          start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
          style={styles.courseCard}
        >
          <Text style={styles.courseEmoji}>{course.emoji}</Text>
          <View style={styles.courseBadge}>
            <Text style={styles.courseBadgeText}>{course.category}</Text>
          </View>
          <Text style={styles.courseTitle}>{course.title}</Text>
          <Text style={styles.courseDesc} numberOfLines={2}>{course.description}</Text>
          <View style={styles.courseMeta}>
            <Text style={styles.courseMetaText}>⏱ {course.duration_min} min</Text>
            <Text style={styles.courseMetaText}>📚 {course.segments} segments</Text>
          </View>
        </LinearGradient>
      </Pressable>
    </Animated.View>
  );
}

function FeatureCard({ feature, index, onPress }: { feature: typeof DEMO_FEATURES[0]; index: number; onPress: () => void }) {
  const { opacity, translateY } = useFadeSlideIn(400 + index * 80);
  const pressScale = useRef(new Animated.Value(1)).current;
  return (
    <Animated.View style={[styles.featureCardWrap, { opacity, transform: [{ translateY }, { scale: pressScale }] }]}>
      <Pressable
        onPress={onPress}
        onPressIn={() => Animated.spring(pressScale, { toValue: 0.96, useNativeDriver: true, tension: 200 }).start()}
        onPressOut={() => Animated.spring(pressScale, { toValue: 1, useNativeDriver: true, tension: 200 }).start()}
        style={styles.featureCard}
      >
        <Text style={styles.featureEmoji}>{feature.emoji}</Text>
        <Text style={styles.featureTitle}>{feature.title}</Text>
        <Text style={styles.featureSubtitle}>{feature.subtitle}</Text>
        <Text style={styles.featureDesc} numberOfLines={3}>{feature.description}</Text>
        <View style={[styles.featureDot, { backgroundColor: feature.color }]} />
      </Pressable>
    </Animated.View>
  );
}

export default function DemoScreen({
  onSelectCourse,
  onOpenFeature,
  onEnterFullApp,
  enabledFlags,
}: {
  onSelectCourse: (courseId: string, title: string) => void;
  onOpenFeature: (featureId: string) => void;
  onEnterFullApp: () => void;
  enabledFlags: Record<string, boolean>;
}) {
  const { opacity: headerOpacity, translateY: headerTranslateY } = useFadeSlideIn(0);
  const ctaScale = useRef(new Animated.Value(1)).current;
  const enabledFeatures = DEMO_FEATURES.filter((feature) => enabledFlags[feature.flagKey] !== false);
  const showCourses = enabledFlags[SALES_DEMO_FLAGS.featuredCourses] !== false;
  const showFullAppCta = enabledFlags[SALES_DEMO_FLAGS.fullAppCta] !== false;

  // Pulse animation on CTA button
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(ctaScale, { toValue: 1.04, duration: 900, useNativeDriver: true }),
        Animated.timing(ctaScale, { toValue: 1, duration: 900, useNativeDriver: true }),
      ])
    ).start();
  }, []);

  return (
    <ScrollView style={styles.bg} contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      {/* Hero header */}
      <Animated.View style={[styles.hero, { opacity: headerOpacity, transform: [{ translateY: headerTranslateY }] }]}>
        <View style={styles.logoWrap}>
          <PulseRing />
          <View style={styles.logoCircle}>
            <Svg width={48} height={48} viewBox="0 0 48 48">
              <Circle cx="24" cy="24" r="20" fill="#6366f1" opacity={0.2} />
              <Path d="M24 8 L38 18 L38 34 L24 42 L10 34 L10 18 Z" fill="none" stroke="#6366f1" strokeWidth="2" />
              <Circle cx="24" cy="24" r="6" fill="#6366f1" />
            </Svg>
          </View>
        </View>
        <View style={styles.demoBadge}>
          <Text style={styles.demoBadgeText}>✨ SALES DEMO</Text>
        </View>
        <Text style={styles.heroTitle}>Salareen</Text>
        <Text style={styles.heroSubtitle}>AI-Powered Education Platform</Text>
        <Text style={styles.heroTagline}>Explore the future of workplace learning</Text>
      </Animated.View>

      {showCourses ? (
        <>
          <Text style={styles.sectionTitle}>Featured Courses</Text>
          <Text style={styles.sectionSub}>5 compliance essentials, powered by AI</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.courseRow}>
            {DEMO_COURSES.map((course, i) => (
              <CourseCard
                key={course.id}
                course={course}
                index={i}
                onPress={() => onSelectCourse(course.id, course.title)}
              />
            ))}
          </ScrollView>
        </>
      ) : null}

      {enabledFeatures.length ? (
        <>
          <Text style={styles.sectionTitle}>What Makes Salareen Different</Text>
          <View style={styles.featuresGrid}>
            {enabledFeatures.map((feature, i) => (
              <FeatureCard
                key={feature.id}
                feature={feature}
                index={i}
                onPress={() => onOpenFeature(feature.id)}
              />
            ))}
          </View>
        </>
      ) : null}

      {showFullAppCta ? (
        <Animated.View style={[styles.ctaWrap, { transform: [{ scale: ctaScale }] }]}>
          <Pressable onPress={onEnterFullApp}>
            <LinearGradient
              colors={["#6366f1", "#8b5cf6"]}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }}
              style={styles.ctaBtn}
            >
              <Text style={styles.ctaBtnText}>🚀  Explore Full Demo</Text>
            </LinearGradient>
          </Pressable>
        </Animated.View>
      ) : null}

      <Text style={styles.footer}>Salareen · AI Education Platform · sales@salareen.com</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: "#07080f" },
  content: { paddingBottom: 60 },
  hero: { alignItems: "center", paddingTop: 64, paddingBottom: 32, paddingHorizontal: 24 },
  logoWrap: { width: 100, height: 100, alignItems: "center", justifyContent: "center", marginBottom: 16 },
  logoCircle: { width: 64, height: 64, borderRadius: 32, backgroundColor: "rgba(99,102,241,0.12)", alignItems: "center", justifyContent: "center" },
  demoBadge: { backgroundColor: "rgba(99,102,241,0.2)", borderRadius: 20, paddingHorizontal: 16, paddingVertical: 6, borderWidth: 1, borderColor: "rgba(99,102,241,0.4)", marginBottom: 12 },
  demoBadgeText: { color: "#a5b4fc", fontSize: 11, fontWeight: "800", letterSpacing: 1.5 },
  heroTitle: { color: "#fff", fontSize: 38, fontWeight: "900", letterSpacing: -0.5 },
  heroSubtitle: { color: "#a5b4fc", fontSize: 16, fontWeight: "600", marginTop: 4 },
  heroTagline: { color: "rgba(255,255,255,0.5)", fontSize: 13, marginTop: 8, textAlign: "center" },
  sectionTitle: { color: "#fff", fontSize: 20, fontWeight: "800", marginHorizontal: 20, marginTop: 28, marginBottom: 4 },
  sectionSub: { color: "rgba(255,255,255,0.45)", fontSize: 13, marginHorizontal: 20, marginBottom: 16 },
  courseRow: { paddingHorizontal: 20, paddingBottom: 8 },
  courseCard: { borderRadius: 20, padding: 22, minHeight: 220, justifyContent: "space-between" },
  courseEmoji: { fontSize: 40, marginBottom: 8 },
  courseBadge: { alignSelf: "flex-start", backgroundColor: "rgba(0,0,0,0.25)", borderRadius: 12, paddingHorizontal: 10, paddingVertical: 3, marginBottom: 10 },
  courseBadgeText: { color: "rgba(255,255,255,0.9)", fontSize: 10, fontWeight: "700", letterSpacing: 0.5 },
  courseTitle: { color: "#fff", fontSize: 17, fontWeight: "800", lineHeight: 22, marginBottom: 8 },
  courseDesc: { color: "rgba(255,255,255,0.75)", fontSize: 12, lineHeight: 17, marginBottom: 12 },
  courseMeta: { flexDirection: "row", gap: 12 },
  courseMetaText: { color: "rgba(255,255,255,0.7)", fontSize: 11, fontWeight: "600" },
  featuresGrid: { flexDirection: "row", flexWrap: "wrap", paddingHorizontal: 12, gap: 12, marginTop: 8 },
  featureCardWrap: { width: (W - 48) / 2 },
  featureCard: { backgroundColor: "rgba(255,255,255,0.05)", borderRadius: 18, padding: 18, borderWidth: 1, borderColor: "rgba(255,255,255,0.08)", minHeight: 170 },
  featureEmoji: { fontSize: 32, marginBottom: 10 },
  featureTitle: { color: "#fff", fontSize: 14, fontWeight: "800", marginBottom: 2 },
  featureSubtitle: { color: "rgba(255,255,255,0.5)", fontSize: 11, fontWeight: "600", marginBottom: 8 },
  featureDesc: { color: "rgba(255,255,255,0.55)", fontSize: 11, lineHeight: 16 },
  featureDot: { width: 6, height: 6, borderRadius: 3, marginTop: 12 },
  ctaWrap: { marginHorizontal: 20, marginTop: 36, marginBottom: 12 },
  ctaBtn: { borderRadius: 16, paddingVertical: 18, alignItems: "center" },
  ctaBtnText: { color: "#fff", fontSize: 17, fontWeight: "800", letterSpacing: 0.3 },
  footer: { color: "rgba(255,255,255,0.2)", fontSize: 11, textAlign: "center", marginTop: 8 },
});
