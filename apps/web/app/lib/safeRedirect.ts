// A post-action redirect target must stay on this site: a path that starts with a single "/" and nothing that a browser
// would read as another origin ("//host", "/\host", "javascript:", full URLs, control characters).
const CONTROL_CHARS = new RegExp("[\\u0000-\\u001f\\u007f]");

export function safeReturnPath(value: string | null | undefined, fallback: string): string {
  const v = String(value ?? "").trim();
  if (!v || v.length > 512) return fallback;
  if (!v.startsWith("/") || v.startsWith("//")) return fallback;
  if (v.includes("\\") || CONTROL_CHARS.test(v)) return fallback;
  try {
    const u = new URL(v, "https://placeholder.invalid");
    if (u.origin !== "https://placeholder.invalid") return fallback;
  } catch {
    return fallback;
  }
  return v;
}
