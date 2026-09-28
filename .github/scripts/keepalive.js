// Loads the Streamlit app in a headless browser so Streamlit Community Cloud registers
// a real view (which resets the inactivity-sleep timer). If the app is asleep it clicks
// the wake button, then CONFIRMS the live app actually rendered — so the job fails loudly
// instead of passing green while the app is still asleep.
// Used by .github/workflows/keep-alive.yml.
const { chromium } = require("playwright");

// Text only the *rendered* Research Library shows — NOT the generic Streamlit
// "gone to sleep" screen. Used to prove the app is really up.
const LIVE_APP = /gender gap in space|Popular topics|Search five databases/i;

(async () => {
  const url = process.env.APP_URL;
  if (!url) { console.error("APP_URL not set"); process.exit(1); }

  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    // Not "networkidle": Streamlit holds a websocket open, so it never idles.
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });

    // A sleeping app renders a wake button (client-side, after the JS boots), so wait
    // for it rather than checking an instantaneous count. Absent => already awake.
    const wake = page.getByRole("button", { name: /get this app back up|wake|back up/i });
    try {
      await wake.first().waitFor({ state: "visible", timeout: 25000 });
      console.log("Sleep screen detected -> clicking wake button");
      await wake.first().click();
    } catch {
      console.log("No wake button appeared (app already awake, or screen reworded)");
    }

    // Confirm the REAL app rendered (the sleep screen also lives inside the Streamlit
    // shell, so [data-testid=stApp] is NOT a valid signal). Generous timeout to cover a
    // cold container boot after waking.
    try {
      await page.getByText(LIVE_APP).first().waitFor({ state: "visible", timeout: 150000 });
      console.log("Live app rendered.");
    } catch {
      console.error("App did not render within the timeout — it may still be asleep "
        + "(wake button missing/reworded, or a slow boot). Failing loudly.");
      process.exit(1);
    }

    // Linger so the websocket session is fully established (a genuine "view").
    await page.waitForTimeout(15000);
    console.log("Done. Page title:", await page.title());
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error("keepalive failed:", e); process.exit(1); });
