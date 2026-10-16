// Same-origin YuNet/SFace weights. The web image downloads them into
// public/vision-models at build time (they are gitignored). The caller passes
// the perception URL as the fallback for local `next dev`, where that static
// copy is not in the tree.

export const VISION_MODEL_STATIC_PREFIX = "/vision-models";

class ModelLoadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ModelLoadError";
  }
}

export function visionModelStaticUrl(name: string): string {
  return `${VISION_MODEL_STATIC_PREFIX}/${encodeURIComponent(name)}`;
}

/** Static file first, then whatever fallback URL the caller supplies. */
export function visionModelCandidateUrls(name: string, fallbackUrl: string): string[] {
  return [visionModelStaticUrl(name), fallbackUrl];
}

/** Each URL is tried once, then once more with a cache reload. No force-cache. */
export async function fetchVisionModel(name: string, fallbackUrl: string): Promise<Uint8Array> {
  let last = "unavailable";
  for (const url of visionModelCandidateUrls(name, fallbackUrl)) {
    for (const cache of ["default", "reload"] as const) {
      try {
        const res = await fetch(url, { cache });
        if (!res.ok) {
          last = String(res.status);
          continue;
        }
        return new Uint8Array(await res.arrayBuffer());
      } catch (reason) {
        last = reason instanceof Error ? reason.message : String(reason);
      }
    }
  }
  throw new ModelLoadError(`could not fetch model ${name}: ${last}`);
}
