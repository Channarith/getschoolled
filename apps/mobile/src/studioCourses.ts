/** Full Course Studio classes. Web shows these on Live Class and Group Class. */

import type { PublicDemo } from "./publicDemos";

export const STUDIO_COURSES = [
  {
    id: "drivers-ed",
    title: "Driver's Education",
    blurb: "The full California permit course, taught by Theodore with xAI. The 10-minute demo is free. The rest is paid unless you are an admin.",
    emoji: "🚗",
    hasDemo: true,
  },
  {
    id: "food-safety",
    title: "Food Health & Safety",
    blurb: "The full California food handler course, taught by Theodore with xAI. Admins take it. Everyone else pays.",
    emoji: "🍽️",
    hasDemo: false,
  },
] as const;

export type StudioCourseId = (typeof STUDIO_COURSES)[number]["id"];

export function studioCourseById(id: string): (typeof STUDIO_COURSES)[number] | undefined {
  return STUDIO_COURSES.find((course) => course.id === id);
}

export function fullClassAllowed(
  registered: boolean,
  enrollmentStatus: string,
  isAdmin = false,
): boolean {
  if (isAdmin) return true;
  return registered && enrollmentStatus.trim().toLowerCase() === "paid";
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
  opts: { accountId?: string; isAdmin?: boolean; presentation?: "audio" } = {},
): string {
  const params = new URLSearchParams();
  params.set("access", access);
  params.set("course", courseId);
  params.set("embed", "mobile");
  if (opts.presentation === "audio") params.set("presentation", "audio");
  if (access === "full") {
    params.set("registered", "1");
    if (opts.isAdmin) params.set("admin", "1");
    else params.set("enrollment", "paid");
  }
  if (opts.accountId) params.set("account", opts.accountId);
  return `/studio?${params.toString()}`;
}

export function studioCourseDemo(
  courseId: StudioCourseId,
  access: "sample" | "full",
  opts: { accountId?: string; isAdmin?: boolean; presentation?: "audio" } = {},
): PublicDemo {
  const course = studioCourseById(courseId);
  const title = course?.title || courseId;
  const heard = opts.presentation === "audio";
  return {
    id: courseId,
    path: studioCoursePath(courseId, access, opts),
    emoji: course?.emoji || "📘",
    title: heard ? `${title} · audio` : title,
    subtitle: access === "full" ? "Full course · xAI" : "10-minute demo · xAI",
    description: course?.blurb || "",
  };
}
