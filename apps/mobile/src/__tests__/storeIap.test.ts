import * as api from "../api";
import { buyCourse, restorePurchases, skuFor, storePlatform, type IapAdapter, type StorePurchase } from "../storeIap";
import { studioSessionScript } from "../studioSession";

jest.mock("../api", () => ({
  getIapProducts: jest.fn(),
  verifyAppleTransaction: jest.fn(),
  verifyGooglePurchase: jest.fn(),
}));

const products = {
  course_id: "drivers-ed",
  products: { apple: "com.x.full", google: "full_course" },
  apple_app_account_token: "apple-token",
  google_obfuscated_account_id: "google-token",
};
const bought: StorePurchase = { productId: "com.x.full", transactionId: "T1", purchaseToken: "" };

function adapter(over: Partial<IapAdapter> = {}): IapAdapter & { finished: StorePurchase[] } {
  const finished: StorePurchase[] = [];
  return {
    finished,
    localizedPrice: async () => "$19.99",
    buy: jest.fn(async () => bought),
    restore: jest.fn(async () => [bought, { productId: "other", transactionId: "T9", purchaseToken: "" }]),
    finish: async (p) => { finished.push(p); },
    ...over,
  };
}

const v = () => ({ apple: jest.fn(async () => ({ status: "paid", order_id: "SAL-1" })), google: jest.fn(async () => ({ status: "paid", order_id: "SAL-2" })) });

beforeEach(() => { (api.getIapProducts as jest.Mock).mockResolvedValue(products); });

describe("store purchase", () => {
  it("picks the product id for the platform", () => {
    expect(skuFor(products, "ios")).toBe("com.x.full");
    expect(skuFor(products, "android")).toBe("full_course");
    expect(storePlatform("web")).toBeNull();
  });

  it("buys with the account token, verifies on the server, and only then finishes the transaction", async () => {
    const a = adapter();
    const verifiers = v();
    expect(await buyCourse("drivers-ed", a, verifiers, "ios")).toEqual({ status: "paid", orderId: "SAL-1" });
    expect(a.buy).toHaveBeenCalledWith({ sku: "com.x.full", platform: "ios", accountToken: "apple-token" });
    expect(verifiers.apple).toHaveBeenCalledWith("T1");
    expect(a.finished).toEqual([bought]);
  });

  it("uses the Google token and purchase token on Android", async () => {
    const a = adapter({ buy: jest.fn(async () => ({ productId: "full_course", transactionId: "", purchaseToken: "PT" })) });
    const verifiers = v();
    await buyCourse("drivers-ed", a, verifiers, "android");
    expect(a.buy).toHaveBeenCalledWith({ sku: "full_course", platform: "android", accountToken: "google-token" });
    expect(verifiers.google).toHaveBeenCalledWith("full_course", "PT");
  });

  it("does not finish the transaction when the server refuses", async () => {
    const a = adapter();
    const verifiers = { ...v(), apple: jest.fn(async () => { throw new Error("409 That purchase belongs to another account."); }) };
    await expect(buyCourse("drivers-ed", a, verifiers, "ios")).rejects.toThrow(/another account/);
    expect(a.finished).toEqual([]);
  });

  it("reports cancel and pending without unlocking", async () => {
    expect(await buyCourse("drivers-ed", adapter({ buy: async () => null }), v(), "ios")).toEqual({ status: "cancelled" });
    const pending = { ...v(), apple: jest.fn(async () => ({ status: "pending" })) };
    const a = adapter();
    expect(await buyCourse("drivers-ed", a, pending, "ios")).toEqual({ status: "pending" });
    expect(a.finished).toEqual([]);
  });

  it("refuses on a platform without a store and when the course is not sold in the app", async () => {
    await expect(buyCourse("drivers-ed", adapter(), v(), "web")).rejects.toThrow(/iPhone and Android/);
    (api.getIapProducts as jest.Mock).mockResolvedValue({ ...products, products: {} });
    await expect(buyCourse("drivers-ed", adapter(), v(), "ios")).rejects.toThrow(/not sold in the app/);
  });
});

describe("restore purchases", () => {
  it("re-verifies only this course's purchases onto the account", async () => {
    const a = adapter();
    const verifiers = v();
    expect(await restorePurchases("drivers-ed", a, verifiers, "ios")).toEqual({ status: "paid", orderId: "SAL-1" });
    expect(verifiers.apple).toHaveBeenCalledTimes(1);
  });

  it("says so when there is nothing to restore", async () => {
    const a = adapter({ restore: async () => [] });
    expect(await restorePurchases("drivers-ed", a, v(), "ios")).toEqual({ status: "nothing_to_restore" });
  });
});

describe("studio session cookie", () => {
  it("is only built for a well-formed token", () => {
    expect(studioSessionScript("abc.def-ghi_1")).toContain("aoep_session=abc.def-ghi_1");
    expect(studioSessionScript(null)).toBeUndefined();
    expect(studioSessionScript('x";alert(1)//')).toBeUndefined();
  });
});
