/**
 * The kids picture-lesson player must actually play.
 *
 * Listing an adventure was never the problem — opening one was. This renders
 * the real screen against a stubbed lesson fetch and walks a learner through a
 * whole lesson: read a scene, answer, advance, and finish with a score.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

const lesson = {
  id: "kids-abc-adventures",
  title: "ABC Adventures",
  emoji: "🔤",
  color: "#7c3aed",
  scenes: [
    {
      title: "A is for Apple",
      instruction: "Say the sound: A, A, apple!",
      pictures: ["🔤", "🍎"],
      labels: ["A", "APPLE"],
      question: "Which picture starts with A?",
      choices: ["🍎 Apple", "🐶 Dog"],
      answer: "🍎 Apple",
    },
    {
      title: "B is for Bear",
      instruction: "Bounce the B sound.",
      pictures: ["🐻"],
      question: "Which picture starts with B?",
      choices: ["🐻 Bear", "🐱 Cat"],
      answer: "🐻 Bear",
    },
  ],
};

// `mock`-prefixed so jest allows referencing them inside the hoisted factories.
const mockGetKidsLesson = jest.fn();
jest.mock("../api", () => ({ getKidsLesson: (id: string) => mockGetKidsLesson(id) }));

const mockSpeakNatural = jest.fn();
jest.mock("../tts", () => ({
  speakNatural: (...args: unknown[]) => mockSpeakNatural(...args),
  stopSpeech: jest.fn(),
}));

import KidsLessonScreen from "../screens/KidsLessonScreen";

describe("KidsLessonScreen", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetKidsLesson.mockResolvedValue(lesson);
  });

  it("plays a lesson end to end and reports the score", async () => {
    const onBack = jest.fn();
    render(<KidsLessonScreen courseId="kids-abc-adventures" onBack={onBack} />);

    // Scene 1 renders with its picture, question and choices.
    expect(await screen.findByText("A is for Apple")).toBeTruthy();
    expect(screen.getByText("Which picture starts with A?")).toBeTruthy();
    expect(screen.getByText("🍎 Apple")).toBeTruthy();
    expect(screen.getByText("1 / 2")).toBeTruthy();

    // It reads the scene aloud: these learners cannot read yet.
    await waitFor(() => expect(mockSpeakNatural).toHaveBeenCalled());
    expect(String(mockSpeakNatural.mock.calls[0][0])).toContain("A is for Apple");

    // Answer correctly, then advance.
    fireEvent.press(screen.getByText("🍎 Apple"));
    fireEvent.press(await screen.findByTestId("kids-lesson-next"));

    expect(await screen.findByText("B is for Bear")).toBeTruthy();
    expect(screen.getByText("2 / 2")).toBeTruthy();

    // Answer the last one wrong, finish, and check the celebration score.
    fireEvent.press(screen.getByText("🐱 Cat"));
    fireEvent.press(await screen.findByTestId("kids-lesson-next"));

    expect(await screen.findByText("Great job!")).toBeTruthy();
    expect(screen.getByText(/got 1 of 2 right/)).toBeTruthy();
  });

  it("requests the lesson it was asked for", async () => {
    render(<KidsLessonScreen courseId="kids-first-words" onBack={jest.fn()} />);
    await waitFor(() => expect(mockGetKidsLesson).toHaveBeenCalledWith("kids-first-words"));
  });

  it("shows a way back when the lesson cannot be loaded", async () => {
    mockGetKidsLesson.mockRejectedValue(new Error("offline"));
    const onBack = jest.fn();
    render(<KidsLessonScreen courseId="kids-abc-adventures" onBack={onBack} />);

    expect(await screen.findByText(/offline/)).toBeTruthy();
    fireEvent.press(screen.getByText("Back to Kids"));
    expect(onBack).toHaveBeenCalled();
  });
});
