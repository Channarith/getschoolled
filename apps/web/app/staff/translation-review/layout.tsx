import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Staff",
  robots: { index: false, follow: false, nocache: true },
};

export default function StaffReviewLayout({ children }: { children: React.ReactNode }) {
  return children;
}
