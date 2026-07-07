import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import IntroSplashScreen, { type IntroSplashMode } from "./components/IntroSplashScreen";
import { getSettings, setSettings } from "./storage";

type IntroSplashContextValue = {
  playFullIntro: () => void;
};

const IntroSplashContext = createContext<IntroSplashContextValue>({
  playFullIntro: () => {},
});

export function useIntroSplash(): IntroSplashContextValue {
  return useContext(IntroSplashContext);
}

/** First-launch intro + optional full replay from Settings. */
export function IntroSplashProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<IntroSplashMode | null>(null);

  useEffect(() => {
    void getSettings().then((s) => {
      if (s.introSplashEnabled && !s.introSplashSeen) {
        setMode("intro");
      }
    });
  }, []);

  const playFullIntro = useCallback(() => {
    setMode("full");
  }, []);

  const finish = useCallback(() => {
    if (mode === "intro") {
      void setSettings({ introSplashSeen: true });
    }
    setMode(null);
  }, [mode]);

  const value = useMemo(() => ({ playFullIntro }), [playFullIntro]);

  return (
    <IntroSplashContext.Provider value={value}>
      {children}
      {mode ? <IntroSplashScreen mode={mode} onFinish={finish} /> : null}
    </IntroSplashContext.Provider>
  );
}
