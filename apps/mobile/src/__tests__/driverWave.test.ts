import { driverWaveScript } from "../driverWave";

describe("on the go waveform", () => {
  test("hides the lesson and draws a waveform for the audio presentation", () => {
    const script = driverWaveScript();
    expect(script).toContain("presentation=audio");
    expect(script).toContain("#teach-title");
    expect(script).toContain("#quiz-box");
    expect(script).toContain("#theodore-live-audio");
    expect(script).toContain("display:block !important");
    expect(script).toContain("salareen-drive-choices");
    expect(script).toContain('aria-label", "Course"');
    expect(script).toContain("salareen-drive-wave");
    expect(script).toContain("course-map");
    expect(script).toContain("% of the course");
    expect(script).toContain("#sample-clock");
    expect(script).toContain("salareen-drive-chrome-hidden");
    expect(script).toContain("#student-cam");
    expect(script).toContain("facingMode");
    expect(script).toContain("/api/studio/learn/camera");
    expect(script).not.toContain("camera stays off");
    expect(script).not.toContain('state:"present"');
    expect(script).not.toContain("presentation=video");
  });
});
