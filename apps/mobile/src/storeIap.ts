/**
 * In-app purchase of a course (App Store / Google Play). The app never decides what is paid: the store charges, the SERVER
 * verifies with the store and records the purchase on the account, and only then does the app finish the transaction and open
 * the class. No web checkout and no payment links inside the app.
 */

import { Platform } from "react-native";

import { getIapProducts, verifyAppleTransaction, verifyGooglePurchase, type IapProducts } from "./api";

export type StorePurchase = { productId: string; transactionId: string; purchaseToken: string };

export interface IapAdapter {
  localizedPrice(sku: string): Promise<string>;
  buy(opts: { sku: string; platform: "ios" | "android"; accountToken: string }): Promise<StorePurchase | null>;
  restore(): Promise<StorePurchase[]>;
  finish(purchase: StorePurchase): Promise<void>;
}

export type IapResult =
  | { status: "paid"; orderId: string }
  | { status: "pending" }
  | { status: "cancelled" }
  | { status: "nothing_to_restore" };

type Verify = {
  apple: typeof verifyAppleTransaction;
  google: typeof verifyGooglePurchase;
};

const verifiers: Verify = { apple: verifyAppleTransaction, google: verifyGooglePurchase };

export function storePlatform(os: string = Platform.OS): "ios" | "android" | null {
  return os === "ios" || os === "android" ? os : null;
}

export function skuFor(products: IapProducts, platform: "ios" | "android"): string {
  return (platform === "ios" ? products.products.apple : products.products.google) || "";
}

async function verify(platform: "ios" | "android", purchase: StorePurchase, v: Verify): Promise<{ status: string; order_id?: string }> {
  return platform === "ios"
    ? v.apple(purchase.transactionId)
    : v.google(purchase.productId, purchase.purchaseToken);
}

/** Store price text (for example "$19.99") to show before the buyer taps Buy; "" when the store has none. */
export async function storePriceLabel(courseId: string, adapter: IapAdapter = rnIapAdapter()): Promise<string> {
  const platform = storePlatform();
  if (!platform) return "";
  try {
    const sku = skuFor(await getIapProducts(courseId), platform);
    return sku ? await adapter.localizedPrice(sku) : "";
  } catch {
    return "";
  }
}

export async function buyCourse(
  courseId: string,
  adapter: IapAdapter = rnIapAdapter(),
  v: Verify = verifiers,
  os: string = Platform.OS,
): Promise<IapResult> {
  const platform = storePlatform(os);
  if (!platform) throw new Error("Purchases are available in the iPhone and Android apps.");
  const products = await getIapProducts(courseId);
  const sku = skuFor(products, platform);
  if (!sku) throw new Error("This course is not sold in the app yet.");
  const accountToken = platform === "ios" ? products.apple_app_account_token : products.google_obfuscated_account_id;
  const purchase = await adapter.buy({ sku, platform, accountToken });
  if (!purchase) return { status: "cancelled" };
  const answer = await verify(platform, purchase, v);
  if (answer.status === "pending") return { status: "pending" };
  await adapter.finish(purchase);
  return { status: "paid", orderId: answer.order_id || "" };
}

/** Restore Purchases: re-verify what the store says this person owns, onto THIS account. Required by App Review. */
export async function restorePurchases(
  courseId: string,
  adapter: IapAdapter = rnIapAdapter(),
  v: Verify = verifiers,
  os: string = Platform.OS,
): Promise<IapResult> {
  const platform = storePlatform(os);
  if (!platform) throw new Error("Purchases are available in the iPhone and Android apps.");
  const products = await getIapProducts(courseId);
  const sku = skuFor(products, platform);
  const mine = (await adapter.restore()).filter((p) => p.productId === sku);
  let last: IapResult = { status: "nothing_to_restore" };
  for (const purchase of mine) {
    const answer = await verify(platform, purchase, v);
    if (answer.status === "pending") {
      last = { status: "pending" };
      continue;
    }
    await adapter.finish(purchase);
    last = { status: "paid", orderId: answer.order_id || "" };
  }
  return last;
}

// react-native-iap is a native module: load it only on a real build, so Expo Go and tests do not crash on import.
function loadNative(): typeof import("react-native-iap") {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require("react-native-iap") as typeof import("react-native-iap");
}

function toStorePurchase(p: { productId: string; transactionId?: string | null; purchaseToken?: string }): StorePurchase {
  return { productId: p.productId, transactionId: String(p.transactionId || ""), purchaseToken: String(p.purchaseToken || "") };
}

export function rnIapAdapter(): IapAdapter {
  let connected = false;
  const iap = () => loadNative();
  const connect = async () => {
    if (!connected) {
      await iap().initConnection();
      connected = true;
    }
  };
  return {
    async localizedPrice(sku) {
      await connect();
      const found = (await iap().getProducts({ skus: [sku] }))[0];
      return found?.localizedPrice || "";
    },
    async buy({ sku, platform, accountToken }) {
      await connect();
      const lib = iap();
      return new Promise<StorePurchase | null>((resolve, reject) => {
        const done = (fn: () => void) => { ok.remove(); bad.remove(); fn(); };
        const ok = lib.purchaseUpdatedListener((p) => {
          if (p.productId === sku) done(() => resolve(toStorePurchase(p)));
        });
        const bad = lib.purchaseErrorListener((e) => {
          done(() => (e.code === "E_USER_CANCELLED" ? resolve(null) : reject(new Error(e.message || "The purchase did not go through."))));
        });
        const started = platform === "ios"
          ? lib.requestPurchase({ sku, appAccountToken: accountToken, andDangerouslyFinishTransactionAutomaticallyIOS: false })
          : lib.requestPurchase({ skus: [sku], obfuscatedAccountIdAndroid: accountToken });
        Promise.resolve(started).catch((err) => done(() => reject(err instanceof Error ? err : new Error("The purchase did not go through."))));
      });
    },
    async restore() {
      await connect();
      return (await iap().getAvailablePurchases()).map(toStorePurchase);
    },
    async finish(purchase) {
      await connect();
      const lib = iap();
      const all = await lib.getAvailablePurchases();
      const match = all.find((p) => p.productId === purchase.productId && String(p.transactionId || "") === purchase.transactionId);
      if (match) await lib.finishTransaction({ purchase: match, isConsumable: false });
    },
  };
}
