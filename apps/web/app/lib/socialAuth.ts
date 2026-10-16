import { loginWithApple, loginWithFacebook, loginWithGoogle } from "./api";

const GOOGLE_CLIENT_ID = "647091395717-scfbmvsudec5t9vqukk2h8k732bgd3kp.apps.googleusercontent.com";
const FACEBOOK_APP_ID = "1071803295271778";
const APPLE_SERVICES_ID = "com.aiclassroom.web";

let googleReady = false;

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

/** Create or sign in to an account with Google, Facebook, or Apple. Returns the session token. */
export async function signInWithSocial(provider: "google" | "facebook" | "apple"): Promise<{ token: string }> {
  if (provider === "google") {
    if (!googleReady) {
      await loadScript("https://accounts.google.com/gsi/client");
      googleReady = true;
    }
    return new Promise((resolve, reject) => {
      (window as any).google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (response: { credential: string }) => {
          try { resolve(await loginWithGoogle(response.credential)); } catch (error) { reject(error); }
        },
      });
      (window as any).google.accounts.id.prompt((notification: any) => {
        if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
          reject(new Error("Google sign-in dismissed"));
        }
      });
    });
  }

  if (provider === "facebook") {
    if (!(window as any).FB) {
      await new Promise<void>((resolve, reject) => {
        (window as any).fbAsyncInit = () => {
          (window as any).FB.init({ appId: FACEBOOK_APP_ID, version: "v19.0", cookie: true, xfbml: false });
          resolve();
        };
        loadScript("https://connect.facebook.net/en_US/sdk.js").catch(reject);
      });
    }
    const token = await new Promise<string>((resolve, reject) => {
      (window as any).FB.login((response: any) => {
        if (response.authResponse?.accessToken) resolve(response.authResponse.accessToken);
        else reject(new Error("Facebook sign-in cancelled"));
      }, { scope: "email,public_profile" });
    });
    return loginWithFacebook(token);
  }

  if (!(window as any).AppleID) {
    await loadScript("https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js");
  }
  (window as any).AppleID.auth.init({
    clientId: APPLE_SERVICES_ID,
    scope: "name email",
    redirectURI: `${window.location.origin}/login`,
    usePopup: true,
  });
  const data = await (window as any).AppleID.auth.signIn();
  return loginWithApple(data?.authorization?.id_token);
}
