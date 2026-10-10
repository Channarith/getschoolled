/** Pre-class camera gate. Continue turns on only after a photo is saved.
 * The green "photo saved" row is a status, not a second button.
 */

export function cameraContinueEnabled(photoSaved: boolean, busy: boolean): boolean {
  return photoSaved && !busy;
}

export function trackingContinueEnabled(
  needsPhoto: boolean,
  photoSaved: boolean,
  busy: boolean,
): boolean {
  if (busy) return false;
  if (!needsPhoto) return true;
  return photoSaved;
}
