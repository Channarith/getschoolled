import { faceDistanceCue, isOnDeviceReaderMissing, readMlKitFace } from "../deviceFace";
import {
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

  it("backs off and stops growing at 15 minutes", () => {
    expect(pendingRetryDelayMs(0)).toBe(15_000);
    expect(pendingRetryDelayMs(1)).toBe(30_000);
    expect(pendingRetryDelayMs(6)).toBe(15 * 60 * 1000);
    expect(pendingRetryDelayMs(40)).toBe(15 * 60 * 1000);
  });
});
