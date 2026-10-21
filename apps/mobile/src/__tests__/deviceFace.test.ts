import { faceDistanceCue, frameVerdict, isOnDeviceReaderMissing, readMlKitFace, type DeviceFaceRead } from "../deviceFace";
import {
  isConsentMissing,
  isDeferredUpload,
  isForeignLearner,
  isRejectedCapture,
  pendingRetryDelayMs,
} from "../pendingUpload";

describe("on-device face read", () => {
  const face = {
    frame: { left: 100, top: 80, width: 200, height: 240 },
    landmarks: {
      rightEye: { position: { x: 140, y: 140 } },
      leftEye: { position: { x: 240, y: 142 } },
      noseBase: { position: { x: 190, y: 190 } },
      mouthRight: { position: { x: 160, y: 230 } },
      mouthLeft: { position: { x: 220, y: 232 } },
    },
    contours: {
      face: { points: [{ x: 100, y: 80 }, { x: 300, y: 80 }, { x: 200, y: 320 }] },
      leftEye: { points: [{ x: 230, y: 140 }, { x: 250, y: 145 }] },
      noseBridge: { points: [{ x: 190, y: 150 }, { x: 192, y: 180 }] },
    },
    smilingProbability: 0.91,
  };

  it("maps ML Kit landmarks into YuNet order and keeps the real contours", () => {
    const read = readMlKitFace(face);
    expect(read?.landmarks).toEqual([
      [140, 140],
      [240, 142],
      [190, 190],
      [160, 230],
      [220, 232],
    ]);
    expect(read?.bbox).toEqual([100, 80, 200, 240]);
    expect(read?.strokes.map((stroke) => stroke.closed)).toEqual([true, true, false]);
    expect(read?.smiling).toBe(0.91);
    expect(read?.faceWidth).toBe(200);
  });

  it("still returns a box when a landmark is missing", () => {
    const partial = readMlKitFace({ ...face, landmarks: { rightEye: face.landmarks.rightEye } });
    expect(partial?.landmarks).toBeNull();
    expect(partial?.strokes.length).toBe(3);
  });

  it("asks the learner to fill the circle", () => {
    expect(faceDistanceCue(80, 1000)).toBe("closer");
    expect(faceDistanceCue(400, 1000)).toBe("ok");
    expect(faceDistanceCue(800, 1000)).toBe("back");
    expect(faceDistanceCue(0, 1000)).toBe("ok");
  });

  it("reads head angle and open eyes for the straight-on check", () => {
    const read = readMlKitFace({
      ...face,
      rotationX: -4,
      rotationY: 9,
      leftEyeOpenProbability: 0.92,
      rightEyeOpenProbability: 0.81,
    });
    expect(read?.yaw).toBe(9);
    expect(read?.pitch).toBe(-4);
    expect(read?.eyesOpen).toBe(0.81);
    expect(readMlKitFace(face)?.eyesOpen).toBeNull();
  });

  it("keeps only a centered, straight-on, open-eyed still", () => {
    const frame: [number, number] = [480, 640];
    const good = (patch: Partial<DeviceFaceRead> = {}): DeviceFaceRead => ({
      landmarks: null,
      bbox: [140, 200, 200, 240],
      strokes: [],
      smiling: null,
      faceWidth: 200,
      yaw: 3,
      pitch: -2,
      eyesOpen: 0.9,
      ...patch,
    });
    expect(frameVerdict([good()], frame)).toBe("ok");
    expect(frameVerdict([], frame)).toBe("none");
    expect(frameVerdict([good(), good({ bbox: [10, 10, 180, 200], faceWidth: 180 })], frame)).toBe("many");
    expect(frameVerdict([good(), good({ bbox: [10, 10, 40, 50], faceWidth: 40 })], frame)).toBe("ok");
    expect(frameVerdict([good({ faceWidth: 60, bbox: [210, 290, 60, 70] })], frame)).toBe("closer");
    expect(frameVerdict([good({ faceWidth: 420, bbox: [30, 110, 420, 460] })], frame)).toBe("back");
    expect(frameVerdict([good({ bbox: [0, 200, 200, 240] })], frame)).toBe("center");
    expect(frameVerdict([good({ yaw: 30 })], frame)).toBe("straight");
    expect(frameVerdict([good({ pitch: -25 })], frame)).toBe("straight");
    expect(frameVerdict([good({ eyesOpen: 0.1 })], frame)).toBe("eyes");
    expect(frameVerdict([good({ eyesOpen: null, yaw: null, pitch: null })], frame)).toBe("ok");
  });

  it("recognizes a build that has not linked the on-device reader", () => {
    expect(isOnDeviceReaderMissing(new Error(
      "The package '@react-native-ml-kit/face-detection' doesn't seem to be linked.",
    ))).toBe(true);
    expect(isOnDeviceReaderMissing(new Error("no face"))).toBe(false);
  });
});

describe("deferred learner-check upload", () => {
  it("keeps a capture when the connection is down", () => {
    expect(isDeferredUpload(Object.assign(new Error("unavailable"), { status: 503 }))).toBe(true);
    expect(isDeferredUpload(new Error("Network request failed"))).toBe(true);
    expect(isDeferredUpload(new Error("Saving the face check is taking too long."))).toBe(true);
    expect(isDeferredUpload(new Error("503 face landmarks are not available"))).toBe(true);
  });

  it("does not keep a capture the server already refused", () => {
    expect(isDeferredUpload(Object.assign(new Error("pose left missing"), { status: 422 }))).toBe(false);
    expect(isDeferredUpload(new Error("422 pose challenge face does not match portrait"))).toBe(false);
    expect(isRejectedCapture(Object.assign(new Error("pose left missing"), { status: 422 }))).toBe(true);
    expect(isDeferredUpload(new Error("student not found"))).toBe(false);
    expect(isDeferredUpload(new Error("Could not save your face check."))).toBe(false);
  });
});

describe("held learner-check retries", () => {
  it("keeps another account's capture on a shared device", () => {
    const notOurs = Object.assign(new Error("student not found"), { status: 404 });
    expect(isForeignLearner(notOurs)).toBe(true);
    expect(isForeignLearner(new Error("401 not signed in"))).toBe(true);
    expect(isForeignLearner(Object.assign(new Error("pose left missing"), { status: 422 }))).toBe(false);
  });

  it("sends the consent again when identity has not seen it yet", () => {
    expect(isConsentMissing(Object.assign(new Error("biometric consent is required"), { status: 409 }))).toBe(true);
    expect(isConsentMissing(new Error("409 biometric consent is required"))).toBe(true);
    expect(isConsentMissing(Object.assign(new Error("game already submitted"), { status: 409 }))).toBe(false);
    expect(isConsentMissing(Object.assign(new Error("consent"), { status: 422 }))).toBe(false);
  });

  it("backs off and stops growing at 15 minutes", () => {
    expect(pendingRetryDelayMs(0)).toBe(15_000);
    expect(pendingRetryDelayMs(1)).toBe(30_000);
    expect(pendingRetryDelayMs(6)).toBe(15 * 60 * 1000);
    expect(pendingRetryDelayMs(40)).toBe(15 * 60 * 1000);
  });
});

import { frameForFaces, scanFailureMessage } from "../deviceFace";

describe("iOS still orientation and scan failure message", () => {
  const face = (left: number, top: number, w: number, h: number): DeviceFaceRead => ({
    landmarks: null, bbox: [left, top, w, h], strokes: [], smiling: null, faceWidth: w, yaw: 0, pitch: 0, eyesOpen: 1,
  });

  it("turns a sideways frame size when the face box only fits upright", () => {
    const faces = [face(210, 480, 300, 340)];
    expect(frameForFaces([1280, 720], faces)).toEqual([720, 1280]);
    expect(frameVerdict(faces, frameForFaces([1280, 720], faces))).toBe("ok");
    expect(frameVerdict(faces, [1280, 720])).toBe("center");
  });

  it("leaves a frame alone when the box already fits", () => {
    expect(frameForFaces([720, 1280], [face(210, 480, 300, 340)])).toEqual([720, 1280]);
    expect(frameForFaces([720, 1280], [])).toEqual([720, 1280]);
  });

  it("tells the learner what the phone actually saw", () => {
    expect(scanFailureMessage({ center: 9, none: 2 })).toMatch(/inside the circle/);
    expect(scanFailureMessage({ eyes: 7, straight: 1 })).toMatch(/eyes/);
    expect(scanFailureMessage({ none: 12 })).toMatch(/clear look/);
    expect(scanFailureMessage({})).toMatch(/clear look/);
  });
});
