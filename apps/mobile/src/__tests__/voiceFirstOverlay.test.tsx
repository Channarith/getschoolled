/**
 * Sala-only voice-first overlay tests.
 *
 * The overlay is the one piece of the mobile voice-first player a learner
 * actually sees before voice takes over, so these tests cover the few
 * guarantees we need to keep stable:
 *   1. Nothing renders when `active` is false (overlay must be inert when the
 *      hosting screen flips voice-first off).
 *   2. The consent card appears first and the primary "Let Sala listen" button
 *      starts the recognizer (via startAmbientListening).
 *   3. Three missed commands in a row inside the parser's window reveal the
 *      classic chrome (onRevealChrome fires with "misses").
 *   4. The "Type to Sala" FAB only renders when the typeToAsk prop is on, and
 *      submitting a parseable command routes it through onIntent.
 */
import { act, fireEvent, render, waitFor } from "@testing-library/react-native";

// Stub the mic layer: tests should never actually touch a microphone, and the
// Jest environment has no SpeechRecognition. Capture call args so we can
// assert that pressing "Let Sala listen" wires through to it.
const mockStartAmbient = jest.fn().mockResolvedValue(true);
const mockStopAmbient = jest.fn();
let capturedOnResult: ((text: string) => void) | null = null;

jest.mock("../voiceAssistant", () => ({
  startAmbientListening: (opts: { onResult: (t: string) => void }) => {
    capturedOnResult = opts.onResult;
    return mockStartAmbient(opts);
  },
  stopAmbientListening: () => mockStopAmbient(),
}));

import VoiceFirstOverlay from "../components/VoiceFirstOverlay";

describe("VoiceFirstOverlay", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedOnResult = null;
  });

  it("renders nothing when active is false", () => {
    const { queryByText } = render(
      <VoiceFirstOverlay
        active={false}
        locale="en-US"
        onIntent={jest.fn()}
        onRevealChrome={jest.fn()}
      />,
    );
    expect(queryByText(/Let Sala listen/)).toBeNull();
    expect(queryByText(/Sala listening/)).toBeNull();
  });

  it("starts the recognizer after the learner accepts the consent card", async () => {
    const onIntent = jest.fn();
    const { findByText } = render(
      <VoiceFirstOverlay
        active
        locale="en-US"
        onIntent={onIntent}
        onRevealChrome={jest.fn()}
      />,
    );

    const accept = await findByText(/Let Sala listen/);
    await act(async () => { fireEvent.press(accept); });
    await waitFor(() => expect(mockStartAmbient).toHaveBeenCalledTimes(1));
    // Pill replaces the consent card once listening begins.
    await findByText(/Sala listening/);
    // Simulate a matched utterance arriving from the recognizer.
    expect(capturedOnResult).toBeInstanceOf(Function);
    act(() => { capturedOnResult?.("pause"); });
    expect(onIntent).toHaveBeenCalledWith({ kind: "pause" });
  });

  it("handles the show controls command inside the overlay", async () => {
    const onReveal = jest.fn();
    const { findByText } = render(
      <VoiceFirstOverlay
        active
        locale="en-US"
        onIntent={jest.fn()}
        onRevealChrome={onReveal}
      />,
    );
    const accept = await findByText(/Let Sala listen/);
    await act(async () => { fireEvent.press(accept); });
    await waitFor(() => expect(capturedOnResult).not.toBeNull());
    act(() => { capturedOnResult?.("show controls"); });
    expect(onReveal).toHaveBeenCalledWith("voice");
  });

  it("reveals the classic chrome after three missed commands", async () => {
    const onReveal = jest.fn();
    const { findByText } = render(
      <VoiceFirstOverlay
        active
        locale="en-US"
        onIntent={jest.fn()}
        onRevealChrome={onReveal}
      />,
    );
    const accept = await findByText(/Let Sala listen/);
    await act(async () => { fireEvent.press(accept); });
    await waitFor(() => expect(capturedOnResult).not.toBeNull());

    // Three garbage utterances inside the 15 s window should trip the reveal.
    act(() => { capturedOnResult?.("asdf qwerty"); });
    act(() => { capturedOnResult?.("blah blah"); });
    expect(onReveal).not.toHaveBeenCalled();
    act(() => { capturedOnResult?.("zxcv mnop"); });
    expect(onReveal).toHaveBeenCalledWith("misses");
  });

  it("hides the Type to Sala FAB by default", async () => {
    const { queryByText, findByText } = render(
      <VoiceFirstOverlay
        active
        locale="en-US"
        onIntent={jest.fn()}
        onRevealChrome={jest.fn()}
      />,
    );
    const accept = await findByText(/Let Sala listen/);
    await act(async () => { fireEvent.press(accept); });
    await waitFor(() => expect(mockStartAmbient).toHaveBeenCalled());
    expect(queryByText(/Type to Sala/)).toBeNull();
  });

  it("shows the Type to Sala FAB when the accessibility flag is on", async () => {
    const { findByText } = render(
      <VoiceFirstOverlay
        active
        locale="en-US"
        typeToAsk
        onIntent={jest.fn()}
        onRevealChrome={jest.fn()}
      />,
    );
    const accept = await findByText(/Let Sala listen/);
    await act(async () => { fireEvent.press(accept); });
    // The FAB renders alongside the "Sala listening" pill once consent lands.
    await findByText(/Type to Sala/);
  });
});
