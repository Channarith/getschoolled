/** Helpers for the Settings camera check live preview. */

/** Resolve once the video element has non-zero intrinsic dimensions. */
export function waitForVideoDimensions(
  video: HTMLVideoElement,
  timeoutMs = 12_000,
): Promise<boolean> {
  if (video.videoWidth > 0 && video.videoHeight > 0) return Promise.resolve(true);
  return new Promise((resolve) => {
    const finish = () => {
      window.clearTimeout(timer);
      video.removeEventListener("loadedmetadata", finish);
      video.removeEventListener("loadeddata", finish);
      video.removeEventListener("playing", finish);
      resolve(video.videoWidth > 0 && video.videoHeight > 0);
    };
    const timer = window.setTimeout(finish, timeoutMs);
    video.addEventListener("loadedmetadata", finish);
    video.addEventListener("loadeddata", finish);
    video.addEventListener("playing", finish);
  });
}

/** Race an async detector call so a hung promise cannot stall the step loop. */
export async function detectWithTimeout<T>(
  promise: Promise<T>,
  timeoutMs = 450,
  fallback: T,
): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | null = null;
  try {
    return await Promise.race([
      promise,
      new Promise<T>((resolve) => {
        timer = setTimeout(() => resolve(fallback), timeoutMs);
      }),
    ]);
  } finally {
    if (timer != null) clearTimeout(timer);
  }
}
