/**
 * Signed-out demos, matching the web demo picker
 * (apps/web/app/lib/salesDemo.ts DEMO_ONLY_FEATURE_IDS).
 * The app opens the lab and the lesson themselves, with embed=mobile, so a
 * phone is not stuck inside the website's headings and a second iframe.
 */

export type PublicDemo = {
  id: string;
  path: string;
  emoji: string;
  title: string;
  subtitle: string;
  description: string;
};

export const PUBLIC_DEMOS: PublicDemo[] = [
  {
    id: "drivers-ed",
    path: "/studio?access=sample&course=drivers-ed&embed=mobile",
    emoji: "🤖",
    title: "Solo AI Session",
    subtitle: "Driver's Ed · 10-min demo",
    description: "A 1:1 tutor that walks you through the free 10-minute driver's ed demo lesson.",
  },
  {
    id: "on-the-go",
    path: "/studio?access=sample&course=drivers-ed&presentation=audio&embed=mobile",
    emoji: "🎧",
    title: "On-the-Go Mode",
    subtitle: "Audio only · 10-min demo",
    description: "The same classes as driver's ed, heard with no camera. The free trial stops at 10 minutes.",
  },
  {
    id: "arcade",
    path: "/children-lab?embed=mobile",
    emoji: "🎮",
    title: "Vision arcade",
    subtitle: "Machine vision for kids",
    description: "Children play webcam games: faces, hands, movement, and listening. The camera stays on this device.",
  },
];

export function publicDemoUrl(webAppUrl: string, path: string): string {
  const base = webAppUrl.replace(/\/$/, "");
  const route = path.startsWith("/") ? path : `/${path}`;
  return `${base}${route}`;
}
