/** Public Course Studio gate: a 10-minute sales sample, or the full class. */

export const COURSE_STUDIO_SAMPLE_MINUTES = 10;
export const COURSE_STUDIO_LIBRARY_ID = "course-studio";
export const PAID_ENROLLMENT_STATUS = "paid";

export function courseStudioOrigin(): string {
  const fromEnv = process.env.NEXT_PUBLIC_COURSE_STUDIO_URL?.trim();
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  return "http://127.0.0.1:8040";
}

/** Full class only when the account exists and this class was paid for. */
export function fullClassAllowed(registered: boolean, enrollmentStatus: string): boolean {
  return registered && enrollmentStatus.trim().toLowerCase() === PAID_ENROLLMENT_STATUS;
}

export function courseStudioFrameSrc(opts: {
  access: "sample" | "full";
  accountId?: string;
}): string {
  const url = new URL("/studio", `${courseStudioOrigin()}/`);
  url.searchParams.set("access", opts.access);
  if (opts.access === "full") {
    url.searchParams.set("registered", "1");
    url.searchParams.set("enrollment", PAID_ENROLLMENT_STATUS);
  }
  if (opts.accountId) url.searchParams.set("account", opts.accountId);
  return url.toString();
}
