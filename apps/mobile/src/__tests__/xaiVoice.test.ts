import {
  closeXaiVoiceSession,
  sendTextTurn,
} from "../xaiVoice";

describe("xaiVoice helpers", () => {
  it("sendTextTurn emits conversation.item.create + response.create", () => {
    const sent: string[] = [];
    const openState = typeof WebSocket !== "undefined" ? WebSocket.OPEN : 1;
    const ws = {
      readyState: openState,
      send: (data: string) => {
        sent.push(data);
      },
    } as unknown as WebSocket;
    sendTextTurn(ws, "What is a fraction?");
    expect(sent).toHaveLength(2);
    expect(JSON.parse(sent[0]).type).toBe("conversation.item.create");
    expect(JSON.parse(sent[1]).type).toBe("response.create");
  });

  it("closeXaiVoiceSession is a no-op for null", () => {
    expect(() => closeXaiVoiceSession(null)).not.toThrow();
    expect(() => closeXaiVoiceSession(undefined)).not.toThrow();
  });
});
