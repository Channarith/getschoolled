import {
  MASCOT_DECODER_FILE,
  MASCOT_MODEL_FILE,
  MASCOT_VIEWER_FILE,
  clipForMascotScene,
  mascotPageFile,
  mascotSourceFor,
  mascotViewerHtml,
} from "../components/MobileMascotMeshy";

describe("mobile Meshy mascot", () => {
  test("account creation waves, and quiet steps rotate the idle set", () => {
    expect(clipForMascotScene({ kind: "flyin-point", pointAt: "down" })).toBe("Big_Wave_Hello");
    expect(clipForMascotScene({ kind: "idle" })).toBe("idle");
    expect(clipForMascotScene({ kind: "age-morph", age: 8 })).toBe("idle");
    expect(clipForMascotScene({ kind: "dance" })).toBe("Boom_Dance");
    expect(clipForMascotScene({ kind: "gaming" })).toBe("Jump_Rope");
  });

  test("the webview page loads the bundled viewer and model, not a CDN", () => {
    const html = mascotViewerHtml("Big_Wave_Hello");
    expect(html).toContain(MASCOT_VIEWER_FILE);
    expect(html).toContain(MASCOT_MODEL_FILE);
    expect(html).toContain('clip: "Big_Wave_Hello"');
    expect(html).not.toContain("http");
    expect(mascotViewerHtml("idle").includes('clip: "idle"')).toBe(true);
  });

  test("local model reads go through XMLHttpRequest before the viewer runs", () => {
    const html = mascotViewerHtml("idle");
    const shim = html.indexOf("XMLHttpRequest");
    expect(shim).toBeGreaterThan(-1);
    expect(shim).toBeLessThan(html.indexOf(`src="${MASCOT_VIEWER_FILE}"`));
  });

  test("the page and the viewer agree on the Draco decoder filename", () => {
    expect(MASCOT_DECODER_FILE).toBe("draco_decoder.js");
    expect(mascotViewerHtml("idle")).toContain(MASCOT_VIEWER_FILE);
  });

  test("iOS opens a real file with read access, Android keeps inline markup", () => {
    const dir = "file:///cache/mascot-meshy-v2/";
    expect(mascotSourceFor("ios", dir, "Big_Wave_Hello")).toEqual({ uri: `${dir}mascot-Big_Wave_Hello.html` });
    const android = mascotSourceFor("android", dir, "idle");
    expect(android).toEqual({ html: mascotViewerHtml("idle"), baseUrl: dir });
    expect(mascotPageFile("../evil clip")).toBe("mascot-evilclip.html");
  });
});
