/** The studio page lives in a WebView and identifies the learner by the same login cookie the website uses. */
export function studioSessionScript(token: string | null): string | undefined {
  if (!token || !/^[A-Za-z0-9._~+/=-]+$/.test(token)) return undefined;
  return `try{document.cookie="aoep_session=${token}; path=/; Secure; SameSite=Lax";}catch(e){}true;`;
}
