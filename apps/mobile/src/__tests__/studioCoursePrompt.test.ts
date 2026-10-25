import { Alert } from "react-native";

import * as api from "../api";
import * as iap from "../storeIap";
import { promptStudioCourse } from "../studioCoursePrompt";

jest.mock("../api", () => ({ getCourseEntitlement: jest.fn() }));
jest.mock("../storeIap", () => ({
  buyCourse: jest.fn(),
  restorePurchases: jest.fn(),
  storePlatform: jest.fn(() => "ios"),
  storePriceLabel: jest.fn(async () => "$19.99"),
}));

const t = (key: string, vars?: Record<string, string | number>) => (vars ? `${key}:${Object.values(vars).join(",")}` : key);
const press = (label: string) => jest.spyOn(Alert, "alert").mockImplementation((_t, _m, buttons) => {
  (buttons?.find((b) => b.text === label) ?? buttons?.find((b) => b.text === "studio.notNow"))?.onPress?.();
});
const ent = (entitlement: string) => (api.getCourseEntitlement as jest.Mock).mockResolvedValue({ entitlement });

afterEach(() => jest.restoreAllMocks());

describe("studio course prompt", () => {
  it.each(["free", "paid"])("opens the full class with no price when the server says %s", async (value) => {
    ent(value);
    const spy = jest.spyOn(Alert, "alert");
    const demo = await promptStudioCourse("drivers-ed", { id: "a" }, undefined, t as never);
    expect(demo?.path).toContain("access=full");
    expect(spy).not.toHaveBeenCalled();
    expect(iap.storePriceLabel).not.toHaveBeenCalled();
  });

  it("anonymous visitors get the demo, never a price", async () => {
    press("studio.demo10");
    const demo = await promptStudioCourse("drivers-ed", null, undefined, t as never);
    expect(demo?.path).toContain("access=sample");
    expect(api.getCourseEntitlement).not.toHaveBeenCalled();
  });

  it("must_pay offers the store purchase and opens the class after the server records it", async () => {
    ent("must_pay");
    press("studio.buy:$19.99");
    (iap.buyCourse as jest.Mock).mockResolvedValue({ status: "paid", orderId: "SAL-1" });
    const demo = await promptStudioCourse("drivers-ed", { id: "a" }, undefined, t as never);
    expect(demo?.path).toContain("access=full");
  });

  it("restore purchases is offered and works", async () => {
    ent("must_pay");
    press("studio.restore");
    (iap.restorePurchases as jest.Mock).mockResolvedValue({ status: "paid", orderId: "SAL-1" });
    expect((await promptStudioCourse("drivers-ed", { id: "a" }, undefined, t as never))?.path).toContain("access=full");
  });

  it("a cancelled or pending purchase never opens the full class", async () => {
    ent("must_pay");
    press("studio.buy:$19.99");
    (iap.buyCourse as jest.Mock).mockResolvedValue({ status: "cancelled" });
    expect(await promptStudioCourse("drivers-ed", { id: "a" }, undefined, t as never)).toBeNull();
    (iap.buyCourse as jest.Mock).mockResolvedValue({ status: "pending" });
    expect(await promptStudioCourse("drivers-ed", { id: "a" }, undefined, t as never)).toBeNull();
  });

  it("a failed entitlement check falls back to the demo, not the full class", async () => {
    (api.getCourseEntitlement as jest.Mock).mockRejectedValue(new Error("offline"));
    press("studio.demo10");
    expect((await promptStudioCourse("drivers-ed", { id: "a" }, undefined, t as never))?.path).toContain("access=sample");
  });
});
