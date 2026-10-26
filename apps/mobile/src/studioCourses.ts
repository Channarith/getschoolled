/** Full Course Studio classes. Web shows these on Live Class and Group Class. */

import type { PublicDemo } from "./publicDemos";

export const STUDIO_COURSES = [
  {
    id: "drivers-ed",
    title: "Driver's Education",
    blurb: "The full California permit course, taught by Serenity with Salane Voice. The 4-minute demo is free. The rest is a one-time purchase unless your account includes it.",
    emoji: "🚗",
    hasDemo: true,
  },
  {
    id: "food-safety",
    title: "Food Health & Safety",
    blurb: "The full California food handler course, taught by Serenity with Salane Voice. Included with some accounts; otherwise a one-time purchase.",
    emoji: "🍽️",
    hasDemo: false,
  },
] as const;

export type StudioCourseId = (typeof STUDIO_COURSES)[number]["id"];

export function studioCourseById(id: string): (typeof STUDIO_COURSES)[number] | undefined {
  return STUDIO_COURSES.find((course) => course.id === id);
}

/** Catalog ids and /learn links that should open a studio course, not Drive Mode. */
export function studioCourseFromLink(id: string, deepLink?: string): StudioCourseId | null {
  const link = (deepLink || "").trim();
  if (link.startsWith("/learn/drivers-ed") || id === "drivers-ed" || id === "course_studio:drivers-ed") {
    return "drivers-ed";
  }
  if (link.startsWith("/learn/food-safety") || id === "food-safety" || id === "course_studio:food-safety") {
    return "food-safety";
  }
  return null;
}

export function studioCoursePath(
  courseId: StudioCourseId,
  access: "sample" | "full",
  opts: { accountId?: string; presentation?: "audio" } = {},
): string {
  const params = new URLSearchParams();
  params.set("access", access);
  params.set("course", courseId);
  params.set("embed", "mobile");
  if (opts.presentation === "audio") params.set("presentation", "audio");
  if (opts.accountId) params.set("account", opts.accountId);
  return `/studio?${params.toString()}`;
}

export function studioCourseDemo(
  courseId: StudioCourseId,
  access: "sample" | "full",
  opts: {
    accountId?: string;
    presentation?: "audio";
    title?: string;
    subtitle?: string;
    description?: string;
  } = {},
): PublicDemo {
  const course = studioCourseById(courseId);
  const title = opts.title || course?.title || courseId;
  const heard = opts.presentation === "audio";
  return {
    id: courseId,
    path: studioCoursePath(courseId, access, opts),
    emoji: course?.emoji || "📘",
    title: opts.title ? title : (heard ? `${title} · audio` : title),
    subtitle:
      opts.subtitle ||
      (access === "full" ? "Full course · Serenity · Sala" : "4-minute demo · Serenity · Sala"),
    description: opts.description || course?.blurb || "",
  };
}
