import type { Metadata } from "next";

// Staff pages are never cached at the edge, so a redeploy shows up on the next load.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Staff",
  robots: { index: false, follow: false, nocache: true },
};

export default function StaffReviewLayout({ children }: { children: React.ReactNode }) {
  return children;
}
