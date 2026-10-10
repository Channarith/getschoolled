import { Alert } from "react-native";

import { getPortfolio, purchaseCourse } from "./api";
import type { PublicDemo } from "./publicDemos";
import {
  fullClassAllowed,
  studioCourseById,
  studioCourseDemo,
  type StudioCourseId,
} from "./studioCourses";

type AccountLike = { id: string; is_admin?: boolean } | null;

function ask(title: string, message: string, buttons: { text: string; value: string }[]): Promise<string> {
  return new Promise((resolve) => {
    Alert.alert(
      title,
      message,
      [
        ...buttons.map((button) => ({
          text: button.text,
          onPress: () => resolve(button.value),
        })),
        { text: "Not now", style: "cancel" as const, onPress: () => resolve("") },
      ],
    );
  });
}

/** Open the full xAI course, or the free demo, using the same pay rule as the website. */
export async function promptStudioCourse(
  courseId: StudioCourseId,
  account: AccountLike,
  presentation?: "audio",
): Promise<PublicDemo | null> {
  const course = studioCourseById(courseId);
  if (!course) return null;
  const opts = { accountId: account?.id, isAdmin: Boolean(account?.is_admin), presentation };

  if (account?.is_admin) return studioCourseDemo(courseId, "full", opts);

  if (!account) {
    if (!course.hasDemo) {
      await ask(course.title, "Sign in to take this course. Admins open the full course. Everyone else pays.", []);
      return null;
    }
    const choice = await ask(course.title, course.blurb, [{ text: "10-minute demo", value: "demo" }]);
    return choice === "demo" ? studioCourseDemo(courseId, "sample", opts) : null;
  }

  let status = "";
  try {
    const portfolio = await getPortfolio();
    status = portfolio.enrollments.find((row) => row.course_id === courseId)?.status || "";
  } catch (err) {
    const message = err instanceof Error ? err.message : "Could not check this course.";
    if (!course.hasDemo) {
      await ask(course.title, message, []);
      return null;
    }
    const choice = await ask(course.title, message, [{ text: "10-minute demo", value: "demo" }]);
    return choice === "demo" ? studioCourseDemo(courseId, "sample", opts) : null;
  }

  if (fullClassAllowed(true, status, false)) return studioCourseDemo(courseId, "full", opts);

  const buttons = [{ text: "Pay for this course", value: "pay" }];
  if (course.hasDemo) buttons.push({ text: "10-minute demo", value: "demo" });
  const choice = await ask(
    course.title,
    "This course is paid. An admin account takes the full course without paying.",
    buttons,
  );
  if (choice === "demo") return studioCourseDemo(courseId, "sample", opts);
  if (choice !== "pay") return null;
  try {
    const enrollment = await purchaseCourse(courseId, course.title);
    if (!fullClassAllowed(true, enrollment.status, false)) {
      await ask(course.title, "Payment was not recorded for this course.", []);
      return course.hasDemo ? studioCourseDemo(courseId, "sample", opts) : null;
    }
    return studioCourseDemo(courseId, "full", opts);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Payment was not recorded.";
    await ask(course.title, message, []);
    return null;
  }
}
