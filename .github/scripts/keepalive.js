// Loads the Streamlit app in a headless browser so Streamlit Community Cloud registers
// a real view (which resets the inactivity-sleep timer). If the app is asleep it clicks
// the wake button, then CONFIRMS the live app actually rendered — so the job fails loudly
// instead of passing green while the app is still asleep.
// Used by .github/workflows/keep-alive.yml.
//
// IMPORTANT: Streamlit Community Cloud serves the SLEEP SCREEN (and wake button) from the
// wrapper page, but embeds the RUNNING app in an iframe (src ".../~/+/"). So the wake
// button is on the main frame, while the app's own text is inside that iframe.
const { chromium } = require("playwright");

// Text only the *rendered* Research Library shows (inside the app iframe) — NOT the
// generic Streamlit "gone to sleep" wrapper. Used to prove the app is really up.
const LIVE_APP = /gender gap in space|Popular topics/i;
const APP_FRAME = 'iframe[src*="/~/+/"]';  // the iframe Streamlit Cloud runs the app in

(async () => {
  const url = process.env.APP_URL;
  if (!url) { console.error("APP_URL not set"); process.exit(1); }

  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    // Not "networkidle": Streamlit holds a websocket open, so it never idles.
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });

    // The wake button (when asleep) is on the wrapper/main frame.
    const wake = page.getByRole("button", { name: /get this app back up|wake|back up/i });
    try {
      await wake.first().waitFor({ state: "visible", timeout: 25000 });
      console.log("Sleep screen detected -> clicking wake button");
      await wake.first().click();
    } catch {
      console.log("No wake button appeared (app already awake, or screen reworded)");
    }

    // Confirm the REAL app rendered — its text lives INSIDE the app iframe. Waking from a
    // deep sleep is a cold container boot, which can take minutes, so wait generously and
    // reload once if the first attempt times out.
    const appIsUp = async (timeout) => {
      try {
        await page.frameLocator(APP_FRAME).getByText(LIVE_APP).first()
          .waitFor({ state: "visible", timeout });
        return true;
      } catch { return false; }
    };
    let up = await appIsUp(300000);            // 5 min — covers a cold boot after wake
    if (!up) {
      console.log("Not rendered yet; reloading and waiting once more...");
      await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
      up = await appIsUp(180000);              // another 3 min
    }
    if (!up) {
      console.error("App did not render within the timeout. Diagnostics:");
      console.error("  page title:", await page.title());
      console.error("  frames:", page.frames().map((f) => f.url()));
      try {
        const t = await page.frameLocator(APP_FRAME).locator("body").innerText();
        console.error("  app-frame text sample:", (t || "").slice(0, 300).replace(/\n+/g, " | "));
      } catch (e) { console.error("  could not read app frame:", e.message); }
      process.exit(1);
    }
    console.log("Live app rendered (text found inside the app iframe).");

    // Linger so the websocket session is fully established (a genuine "view").
    await page.waitForTimeout(15000);
    console.log("Done. Page title:", await page.title());
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error("keepalive failed:", e); process.exit(1); });
