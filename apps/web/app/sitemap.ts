import type { MetadataRoute } from "next";

const SITE = "https://www.salareen.com";

// Public pages only: no staff, admin, account, billing, or per-user routes.
const PATHS = [
  "/",
  "/our-story",
  "/contact",
  "/demo",
  "/demo/drivers-ed",
  "/demo/arcade",
  "/download",
  "/languages",
  "/kids",
  "/corporate",
  "/jobs",
  "/group-classes",
  "/training",
  "/vision",
  "/arcade",
  "/security",
  "/transparency",
  "/model-cards",
  "/legal",
  "/privacy",
  "/terms",
  "/legal/sweepstakes-rules",
  "/data-deletion",
];

export default function sitemap(): MetadataRoute.Sitemap {
  return PATHS.map((path) => ({ url: `${SITE}${path === "/" ? "" : path}` }));
}
