import { execFileSync } from "child_process";
import fs from "fs";
import path from "path";
import { defineConfig, devices } from "@playwright/test";

/**
 * Learner Check end to end, with a fake camera, a fake microphone, and the
 * mock face engine (?learnerCheckMock=1). Identity and perception are real.
 *
 *   npx playwright test -c playwright.learner-check.config.ts
 *
 * E2E_BASE_URL         web origin (default http://localhost:3000)
 * E2E_IDENTITY_URL     identity the test signs up against (default http://localhost:8008)
 * E2E_IDENTITY_TARGET  when set, the page's calls to :8008 are sent here instead,
 *                      so a separate identity can be tested without rebuilding the web app.
 *
 * The microphone plays a spoken sentence made with macOS `say` when it is
 * available, otherwise Chrome's built-in tone.
 */
const AUDIO = path.resolve(__dirname, "e2e/.media/voice-check.wav");

function speechFile(): string | null {
  if (fs.existsSync(AUDIO) && fs.statSync(AUDIO).size > 200_000) return AUDIO;
  fs.mkdirSync(path.dirname(AUDIO), { recursive: true });
  const aiff = AUDIO.replace(/\.wav$/, ".aiff");
  try {
    execFileSync("say", [
      "-r", "150", "-o", aiff,
      "Today I am ready to learn with Salareen. Can you hear my voice clearly? "
        + "Yes, I am speaking naturally and confidently. One, two, three, four, five.",
    ]);
    // `say` leaves an empty file when speech synthesis is unavailable.
    if (fs.statSync(aiff).size > 64_000) {
      execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-i", aiff, "-ac", "1", "-ar", "48000", AUDIO]);
      return AUDIO;
    }
  } catch {
    /* fall through to the voiced tone */
  } finally {
    fs.rmSync(aiff, { force: true });
  }
  try {
    execFileSync("ffmpeg", [
      "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=180:duration=14",
      "-af", "tremolo=f=3:d=0.6,volume=0.6", "-ac", "1", "-ar", "48000", AUDIO,
    ]);
    return AUDIO;
  } catch {
    return null;
  }
}

const audio = speechFile();

export default defineConfig({
  testDir: "./e2e/learner-check",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  retries: 0,
  reporter: [["line"]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    permissions: ["camera", "microphone"],
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: {
          args: [
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            ...(audio ? [`--use-file-for-fake-audio-capture=${audio}`] : []),
          ],
        },
      },
    },
  ],
});
