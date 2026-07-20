const ATTENDEE_CODES: Record<string, string> = {};

export function setAttendeeCode(key: string, code: string): void {
  const k = (key || "").trim();
  const v = (code || "").trim();
  if (!k) return;
  if (!v) {
    delete ATTENDEE_CODES[k];
    return;
  }
  ATTENDEE_CODES[k] = v;
}

export function getAttendeeCode(key: string): string {
  const k = (key || "").trim();
  if (!k) return "";
  return ATTENDEE_CODES[k] || "";
}
