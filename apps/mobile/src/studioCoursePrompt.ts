import { Alert } from "react-native";

import { getCourseEntitlement } from "./api";
import { buyCourse, restorePurchases, storePlatform, storePriceLabel, type IapResult } from "./storeIap";
import type { StringKey } from "./i18n";
import type { PublicDemo } from "./publicDemos";
import {
  studioCourseById,
  studioCourseDemo,
  type StudioCourseId,
} from "./studioCourses";

type AccountLike = { id: string } | null;
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

/**
 * Open the full course or the free demo. The SERVER decides (GET /api/studio/entitlement): free (admin, VIP, premium) and paid
 * go straight in with no price anywhere; only must_pay sees the store purchase. Purchases are App Store / Google Play only.
 */
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
    presentation,
    title: heard ? t("studio.audioTitle", { title: copy.title }) : copy.title,
    subtitle: access === "full" ? t("studio.fullSub") : t("studio.demoSub"),
    description: copy.blurb,
  });
  const notNow = t("studio.notNow");
  const demoButton = { text: t("studio.demo10"), value: "demo" };
  const demoOrNothing = async (message: string): Promise<PublicDemo | null> => {
    const choice = await ask(copy.title, message, course.hasDemo ? [demoButton] : [], notNow);
    return choice === "demo" ? open("sample") : null;
  };

  if (!account) return demoOrNothing(course.hasDemo ? copy.blurb : t("studio.signIn"));

  let entitlement = "";
  try {
    entitlement = (await getCourseEntitlement(courseId)).entitlement;
  } catch (err) {
    return demoOrNothing(err instanceof Error ? err.message : t("studio.checkFailed"));
  }
  if (entitlement === "free" || entitlement === "paid") return open("full");
  if (entitlement !== "must_pay") return demoOrNothing(t("studio.signIn"));

  const price = await storePriceLabel(courseId);
  const buttons = [{ text: price ? t("studio.buy", { price }) : t("studio.pay"), value: "buy" }, { text: t("studio.restore"), value: "restore" }];
  if (course.hasDemo) buttons.push(demoButton);
  const choice = await ask(copy.title, t("studio.paidNote"), buttons, notNow);
  if (choice === "demo") return open("sample");
  if (choice !== "buy" && choice !== "restore") return null;
  try {
    if (!storePlatform()) throw new Error(t("studio.notInApp"));
    const result: IapResult = choice === "buy" ? await buyCourse(courseId) : await restorePurchases(courseId);
    if (result.status === "paid") return open("full");
    if (result.status === "cancelled") return null;
    await ask(copy.title, result.status === "pending" ? t("studio.pending") : t("studio.restoreNone"), [], notNow);
    return null;
  } catch (err) {
    await ask(copy.title, err instanceof Error ? err.message : t("studio.paymentMissing"), [], notNow);
    return null;
  }
}
