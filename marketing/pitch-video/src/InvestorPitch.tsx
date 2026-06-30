import React from "react";
import { AbsoluteFill, Series } from "remotion";
import { COLORS, SCENES } from "./theme";
import {
  Close,
  Features,
  Hook,
  Problem,
  Reveal,
  Safety,
  Scale,
} from "./scenes";

export const InvestorPitch: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bgDeep }}>
      <Series>
        <Series.Sequence durationInFrames={SCENES.hook}>
          <Hook durationInFrames={SCENES.hook} />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.problem}>
          <Problem durationInFrames={SCENES.problem} />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.reveal}>
          <Reveal durationInFrames={SCENES.reveal} />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.features}>
          <Features durationInFrames={SCENES.features} />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.safety}>
          <Safety durationInFrames={SCENES.safety} />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.scale}>
          <Scale durationInFrames={SCENES.scale} />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENES.close}>
          <Close durationInFrames={SCENES.close} />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
