import { LEARNING_PHRASES, phrasesFor } from "../learningPhrases";

const LIKED = [
  "Guided practice",
  "Live lessons",
  "Coached learning",
  "Building intelligence with tech",
  "Video and audio assistive learning",
  "Teacher-led practice",
  "Understanding how you learn",
  "Your private 24/7 tutor",
  "Live lessons available — book your teacher",
  "Practicing through and through",
];

describe("learning phrases", () => {
  test("uses the friendly set and never the old AI-instructed label", () => {
    expect(phrasesFor("en")).toEqual(LIKED);
    expect(phrasesFor("nl")).toEqual(LIKED);
    for (const lines of Object.values(LEARNING_PHRASES)) {
      expect(lines).toHaveLength(LIKED.length);
      for (const line of lines) {
        expect(line.trim().length).toBeGreaterThan(3);
        expect(line.toLowerCase()).not.toContain("ai-instructed");
      }
    }
  });
});
