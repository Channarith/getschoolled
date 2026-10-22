import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";

import LearningProfileSurvey from "../components/LearningProfileSurvey";
import { LEARNING_MODES, savedModalityRatings } from "../learningModes";

const mockSubmit = jest.fn(async () => ({ student: {}, learner_category: "visual_learner", recorded: true }));
jest.mock("../api", () => ({
  getMe: jest.fn(async () => ({ id: "acct-1", display_name: "Maya", email: "maya@example.com" })),
  listStudents: jest.fn(async () => ({
    students: [{
      id: "stu-1",
      onboarding_completed_at: 1,
      onboarding_answers: { modality_ratings: { video: 3, reading: 9, gaming: 99, bogus: 5 } },
    }],
  })),
  createStudent: jest.fn(),
  submitLearningProfile: (...args: unknown[]) => (mockSubmit as unknown as (...a: unknown[]) => unknown)(...args),
  submitOnboardingSurveyAnalytics: jest.fn(async () => ({})),
}));
jest.mock("../storage", () => ({ getToken: () => "token", setSettings: jest.fn(async () => undefined) }));

jest.setTimeout(20000);

describe("learning profile questions in Settings", () => {
  it("keeps only valid saved ratings for the six modes", () => {
    expect(savedModalityRatings({ modality_ratings: { video: 3, reading: 9, gaming: 99, bogus: 5, tutoring: "7" } }))
      .toEqual({ video: 3, reading: 9, tutoring: 7 });
    expect(savedModalityRatings(undefined)).toEqual({});
    expect(savedModalityRatings({ modality_ratings: "x" })).toEqual({});
  });

  it("asks the same six questions as setup, one per page, and saves all six ratings", async () => {
    const view = render(<LearningProfileSurvey manualOpenToken={1} />);
    await waitFor(() => expect(view.getByText(LEARNING_MODES[0].label)).toBeTruthy(), { timeout: 3000 });
    expect(view.getByText(/Step 1 of 6/)).toBeTruthy();
    // No face or voice step, and no old questionnaire.
    expect(view.queryByText(/face|voice|camera/i)).toBeNull();

    for (let i = 0; i < LEARNING_MODES.length; i += 1) {
      expect(view.getByText(LEARNING_MODES[i].label)).toBeTruthy();
      fireEvent.press(view.getByLabelText(`${LEARNING_MODES[i].label}: 8 of 10`));
      fireEvent.press(view.getByText(i === LEARNING_MODES.length - 1 ? "Save changes" : "Next"));
    }
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));
    const [studentId, answers] = mockSubmit.mock.calls[0] as unknown as [string, { modality_ratings: Record<string, number> }];
    expect(studentId).toBe("stu-1");
    expect(answers.modality_ratings).toEqual(Object.fromEntries(LEARNING_MODES.map((m) => [m.id, 8])));
    await waitFor(() => expect(view.getByText(/Profile saved/)).toBeTruthy());
    view.unmount();
  });
});
