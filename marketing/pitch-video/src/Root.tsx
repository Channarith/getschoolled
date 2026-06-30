import React from "react";
import { Composition } from "remotion";
import { InvestorPitch } from "./InvestorPitch";
import { TOTAL_FRAMES, VIDEO } from "./theme";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="InvestorPitch"
        component={InvestorPitch}
        durationInFrames={TOTAL_FRAMES}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
      />
      <Composition
        id="InvestorPitchSquare"
        component={InvestorPitch}
        durationInFrames={TOTAL_FRAMES}
        fps={VIDEO.fps}
        width={1080}
        height={1080}
      />
    </>
  );
};
