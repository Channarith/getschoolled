/** Public Course Studio gate: a free driver's ed demo, or a paid full course. */

export const COURSE_STUDIO_SAMPLE_MINUTES = 10;
export const PAID_ENROLLMENT_STATUS = "paid";

export const PUBLIC_COURSES = [
  {
    id: "drivers-ed",
    title: "Driver's Education",
    href: "/learn/drivers-ed",
    demoHref: "/demo/drivers-ed",
    blurb: "The 10-minute demo is free for anyone. The full course is paid unless you are an admin.",
  },
  {
    id: "food-safety",
    title: "Food Health & Safety",
    href: "/learn/food-safety",
    demoHref: "",
    blurb: "Admins take this course. Everyone else pays.",
  },
] as const;

export type PublicCourseId = (typeof PUBLIC_COURSES)[number]["id"];

/** Full class for an admin, or for a registered account that paid for this course. */
export function fullClassAllowed(
  registered: boolean,
  enrollmentStatus: string,
  isAdmin = false,
): boolean {
  if (isAdmin) return true;
  return registered && enrollmentStatus.trim().toLowerCase() === PAID_ENROLLMENT_STATUS;
}

export function courseStudioFrameSrc(opts: {
  access: "sample" | "full";
  course: PublicCourseId;
  accountId?: string;
  isAdmin?: boolean;
  presentation?: "audio";
}): string {
  const fromEnv = process.env.NEXT_PUBLIC_COURSE_STUDIO_URL?.trim().replace(/\/$/, "") || "";
  const url = new URL("/studio", fromEnv ? `${fromEnv}/` : "http://studio.local/");
  url.searchParams.set("access", opts.access);
  url.searchParams.set("course", opts.course);
  if (opts.presentation === "audio") url.searchParams.set("presentation", "audio");
  if (opts.access === "full") {
    url.searchParams.set("registered", "1");
    if (opts.isAdmin) url.searchParams.set("admin", "1");
    else url.searchParams.set("enrollment", PAID_ENROLLMENT_STATUS);
  }
  if (opts.accountId) url.searchParams.set("account", opts.accountId);
  if (!fromEnv) return `${url.pathname}?${url.searchParams.toString()}`;
  return url.toString();
}
