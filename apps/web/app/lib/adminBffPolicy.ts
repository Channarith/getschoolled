// The admin BFF used to forward any X-Admin-Secret a visitor typed to the memory service, which turned a public route into an
// unthrottled guessing oracle for a shared secret. In a cloud deployment only an identity-verified admin session passes; set
// ADMIN_BFF_ALLOW_SECRET_HEADER=1 to bring the header fallback back for an operator script, or run local/dev/test.
export function secretHeaderFallbackAllowed(env: Record<string, string | undefined> = process.env): boolean {
  if ((env.ADMIN_BFF_ALLOW_SECRET_HEADER || "") === "1") return true;
  const mode = (env.DEPLOY_MODE || "local").toLowerCase();
  return ["local", "dev", "development", "test", "debug"].includes(mode);
}
