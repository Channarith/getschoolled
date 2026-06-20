// Salarean Kids mascots - Angkorian-culture-inspired companion
// characters for the /kids experience. Each mascot is a sticker-style
// PNG (transparent background) generated from the AI image pipeline,
// rendered into webp variants by scripts/build_salarean_brand.py
// (see also docs/brand/mascots/).
//
// To swap which mascot greets kids, change ACTIVE_MASCOT below. All
// four images already ship in apps/web/public/.

export type MascotId = "apsara" | "bayon" | "naga" | "garuda";

export type Mascot = {
  id: MascotId;
  name: string;          // friendly first-name shown in greetings
  altLong: string;       // descriptive alt for screen readers
  image: string;         // /mascot-<id>.webp
  imageSm: string;       // /mascot-<id>-sm.webp (192 px)
  /** Source of the cultural reference - shown in About / Branding pages. */
  origin: string;
  /** First-person greeting line on the Kids hero ("Hi! I'm <name> - ..."). */
  greeting: string;
};

export const MASCOTS: Record<MascotId, Mascot> = {
  apsara: {
    id: "apsara",
    name: "Lily the Apsara",
    altLong:
      "Lily, a young Apsara dancer mascot wearing the Khmer mokot crown, " +
      "holding an open book - inspired by the celestial dancers carved at " +
      "Angkor Wat",
    image: "/mascot-apsara.webp",
    imageSm: "/mascot-apsara-sm.webp",
    origin:
      "Angkor Wat Apsara dancer - the celestial dancer figures carved on " +
      "the temple's walls",
    greeting: "let's discover something new today!",
  },
  bayon: {
    id: "bayon",
    name: "Bayon Buddy",
    altLong:
      "Bayon Buddy, a round cheerful temple-stone character with the " +
      "iconic Bayon smile, holding a glowing lightbulb of wisdom",
    image: "/mascot-bayon.webp",
    imageSm: "/mascot-bayon-sm.webp",
    origin:
      "Bayon Temple's smiling stone faces - the famous serene faces atop " +
      "the towers of Angkor Thom",
    greeting: "I'll smile with you while you learn!",
  },
  naga: {
    id: "naga",
    name: "Naga the Wise",
    altLong:
      "Naga the Wise, a five-headed serpent mascot wearing a graduation " +
      "cap, curled around an open book - the temple guardian of Angkor",
    image: "/mascot-naga.webp",
    imageSm: "/mascot-naga-sm.webp",
    origin:
      "Naga - the multi-headed serpent that guards every Angkor temple " +
      "and symbolises wisdom in Khmer Buddhism",
    greeting: "five heads are better than one - let's read together!",
  },
  garuda: {
    id: "garuda",
    name: "Garuda Glider",
    altLong:
      "Garuda Glider, a baby Garuda chick with golden feathers, " +
      "graduation cap, holding an open book - Cambodia's royal emblem",
    image: "/mascot-garuda.webp",
    imageSm: "/mascot-garuda-sm.webp",
    origin:
      "Garuda - the legendary bird-man, Cambodia's national emblem and " +
      "the celestial vehicle of Vishnu",
    greeting: "spread your wings and learn to soar!",
  },
};

// Default mascot for the Kids experience. Swap to any of the above
// to change every kids-facing surface that uses MASCOTS[ACTIVE_MASCOT].
export const ACTIVE_MASCOT: MascotId = "apsara";
