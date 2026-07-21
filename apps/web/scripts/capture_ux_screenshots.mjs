import { chromium, devices } from "playwright-core";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const outDir = join(process.cwd(), "..", "..", "docs", "screens");
mkdirSync(outDir, { recursive: true });

const WEB_BASE = process.env.WEB_BASE || "http://127.0.0.1:3010";
const MOBILE_BASE = process.env.MOBILE_BASE || "http://127.0.0.1:19007";

async function waitForServer(url, label, attempts = 40) {
  for (let i = 0; i < attempts; i += 1) {
    try {
      const res = await fetch(url, { redirect: "manual" });
      if (res.status < 500) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw new Error(`${label} not ready at ${url}`);
}

async function captureWeb(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${WEB_BASE}/`, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(outDir, "web-home.png"), fullPage: false });

  await page.goto(`${WEB_BASE}/arcade`, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(outDir, "web-arcade.png"), fullPage: true });

  await page.goto(`${WEB_BASE}/drive`, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(outDir, "web-drive.png"), fullPage: false });

  await page.close();
}

async function captureMobile(browser) {
  const context = await browser.newContext({
    ...devices["iPhone 13"],
    viewport: { width: 390, height: 844 },
  });
  const page = await context.newPage();
  await page.goto(MOBILE_BASE, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForTimeout(3000);

  const guestBtn = page.getByRole("button", { name: /browse|guest|preview/i });
  if (await guestBtn.count()) {
    await guestBtn.first().click();
    await page.waitForTimeout(2500);
  }

  await page.screenshot({ path: join(outDir, "mobile-home.png"), fullPage: false });

  const arcadeBtn = page.getByRole("button", { name: /arcade/i });
  if (await arcadeBtn.count()) {
    await arcadeBtn.first().click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: join(outDir, "mobile-arcade.png"), fullPage: true });
  }

  const liveBtn = page.getByRole("button", { name: /live 1:1|live/i });
  if (await liveBtn.count()) {
    await page.goBack().catch(() => {});
    await page.waitForTimeout(1000);
    if (await liveBtn.count()) {
      await liveBtn.first().click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: join(outDir, "mobile-live-class.png"), fullPage: false });
    }
  }

  await context.close();
}

await waitForServer(WEB_BASE, "Web dev server");
await waitForServer(MOBILE_BASE, "Mobile preview");

const launchOpts = { headless: true };
if (process.env.CHROMIUM_PATH) {
  launchOpts.executablePath = process.env.CHROMIUM_PATH;
} else if (process.env.CHROME_CHANNEL) {
  launchOpts.channel = process.env.CHROME_CHANNEL;
}
const browser = await chromium.launch(launchOpts);
try {
  await captureWeb(browser);
  await captureMobile(browser);
  console.log(`Saved screenshots to ${outDir}`);
} finally {
  await browser.close();
}
