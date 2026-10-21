/**
 * Where a catalog card should open.
 *
 * Kids picture adventures and arcade games are not audio courses, so sending
 * every card to Drive Mode (the old behaviour) left them unopenable on mobile
 * even though the rails listed them. Web routes on the card's `deep_link`;
 * this is the same rule for the app.
 */
export type CatalogRoute =
  | { kind: "kidsLesson"; courseId: string }
  | { kind: "game"; subject: string }
  | { kind: "lesson"; lessonId: string }
  | { kind: "drive"; courseId: string };

function queryValue(link: string, key: string): string {
  const match = link.match(new RegExp(`[?&]${key}=([^&]+)`));
  return match ? decodeURIComponent(match[1]) : "";
}

export function routeForCatalogItem(id: string, deepLink?: string): CatalogRoute {
  const link = (deepLink || "").trim();

  const kidsCourse = link.startsWith("/kids/learn") ? queryValue(link, "course") : "";
  if (kidsCourse) return { kind: "kidsLesson", courseId: kidsCourse };

  const subject = link.startsWith("/arcade") ? queryValue(link, "subject") : "";
  if (subject) return { kind: "game", subject };

  // Live classes (CPR and the rest of the lesson catalog) are not audio courses.
  // Sending them to Drive leaves the player spinning on an id it cannot load.
  const lessonId = link.startsWith("/class") || link.startsWith("/corporate/learn")
    ? queryValue(link, "lesson")
    : "";
  if (lessonId) return { kind: "lesson", lessonId };

  const driveCourse = link.startsWith("/drive") ? queryValue(link, "course") : "";
  if (driveCourse) return { kind: "drive", courseId: driveCourse };

  return { kind: "drive", courseId: id };
}
