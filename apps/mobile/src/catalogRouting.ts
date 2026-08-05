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
  | { kind: "drive"; courseId: string };

export function routeForCatalogItem(id: string, deepLink?: string): CatalogRoute {
  const link = (deepLink || "").trim();

  const kidsLesson = link.match(/^\/kids\/learn\?course=([^&]+)/);
  if (kidsLesson) return { kind: "kidsLesson", courseId: decodeURIComponent(kidsLesson[1]) };

  const arcade = link.match(/^\/arcade\?subject=([^&]+)/);
  if (arcade) return { kind: "game", subject: decodeURIComponent(arcade[1]) };

  return { kind: "drive", courseId: id };
}
