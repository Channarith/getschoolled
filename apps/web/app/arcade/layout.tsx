import type { ReactNode } from "react";

import ArcadeTutorial from "../components/ArcadeTutorial";

export default function ArcadeLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <ArcadeTutorial />
      {children}
    </>
  );
}
