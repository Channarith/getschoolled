import { driverWaveScript } from "../driverWave";

describe("on the go waveform", () => {
  test("hides the lesson and draws a waveform for the audio presentation", () => {
    const script = driverWaveScript();
    expect(script).toContain("presentation=audio");
    expect(script).toContain("#teach-title");
    expect(script).toContain("#quiz-box");
    expect(script).toContain("#theodore-live-audio");
    expect(script).toContain("salareen-drive-wave");
    expect(script).toContain("/learn/camera");
    expect(script).toContain("constraints.video");
    expect(script).not.toContain("presentation=video");
  });
});
