import { Alert } from "react-native";

import { getPortfolio, purchaseCourse } from "./api";
import type { StringKey } from "./i18n";
import type { PublicDemo } from "./publicDemos";
import {
  fullClassAllowed,
  studioCourseById,
  studioCourseDemo,
  type StudioCourseId,
} from "./studioCourses";

type AccountLike = { id: string; is_admin?: boolean } | null;
type Translate = (key: StringKey, vars?: Record<string, string | number>) => string;

function ask(
  title: string,
  message: string,
  buttons: { text: string; value: string }[],
  notNow: string,
): Promise<string> {
  return new Promise((resolve) => {
    Alert.alert(
      title,
      message,
      [
        ...buttons.map((button) => ({
          text: button.text,
          onPress: () => resolve(button.value),
        })),
        { text: notNow, style: "cancel" as const, onPress: () => resolve("") },
      ],
    );
  });
}

function courseCopy(t: Translate, courseId: StudioCourseId) {
  if (courseId === "drivers-ed") {
    return { title: t("studio.driversTitle"), blurb: t("studio.driversBlurb") };
  }
  return { title: t("studio.foodTitle"), blurb: t("studio.foodBlurb") };
}

/** Open the full xAI course, or the free demo, using the same pay rule as the website. */
export async function promptStudioCourse(
  courseId: StudioCourseId,
  account: AccountLike,
  presentation: "audio" | undefined,
  t: Translate,
): Promise<PublicDemo | null> {
  const course = studioCourseById(courseId);
  if (!course) return null;
  const copy = courseCopy(t, courseId);
  const heard = presentation === "audio";
  const open = (access: "sample" | "full") => studioCourseDemo(courseId, access, {
    accountId: account?.id,
    isAdmin: Boolean(account?.is_admin),
    presentation,
    title: heard ? t("studio.audioTitle", { title: copy.title }) : copy.title,
    subtitle: access === "full" ? t("studio.fullSub") : t("studio.demoSub"),
    description: copy.blurb,
  });
  const notNow = t("studio.notNow");
  const demoButton = { text: t("studio.demo10"), value: "demo" };

  if (account?.is_admin) return open("full");

  if (!account) {
    if (!course.hasDemo) {
      await ask(copy.title, t("studio.signIn"), [], notNow);
      return null;
    }
    const choice = await ask(copy.title, copy.blurb, [demoButton], notNow);
    return choice === "demo" ? open("sample") : null;
  }

  let status = "";
  try {
    const portfolio = await getPortfolio();
    status = portfolio.enrollments.find((row) => row.course_id === courseId)?.status || "";
  } catch (err) {
    const message = err instanceof Error ? err.message : t("studio.checkFailed");
    if (!course.hasDemo) {
      await ask(copy.title, message, [], notNow);
      return null;
    }
    const choice = await ask(copy.title, message, [demoButton], notNow);
    return choice === "demo" ? open("sample") : null;
  }

  if (fullClassAllowed(true, status, false)) return open("full");

  const buttons = [{ text: t("studio.pay"), value: "pay" }];
  if (course.hasDemo) buttons.push(demoButton);
  const choice = await ask(copy.title, t("studio.paidNote"), buttons, notNow);
  if (choice === "demo") return open("sample");
  if (choice !== "pay") return null;
  try {
    const enrollment = await purchaseCourse(courseId, copy.title);
    if (!fullClassAllowed(true, enrollment.status, false)) {
      await ask(copy.title, t("studio.paymentMissing"), [], notNow);
      return course.hasDemo ? open("sample") : null;
    }
    return open("full");
  } catch (err) {
    const message = err instanceof Error ? err.message : t("studio.paymentMissing");
    await ask(copy.title, message, [], notNow);
    return null;
  }
}
