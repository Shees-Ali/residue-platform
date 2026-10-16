import { expect, test } from "@playwright/test";
import { admin, browserFor, person, reportLot, retire } from "./support";

// EV6: when the live listener is down the person is told, and the screens still catch up.
test("with Firestore blocked, the page says so and still refreshes; unblocked, it goes live again", async ({ browser, request }) => {
  test.setTimeout(240_000);
  const boss = await admin(request);
  const farmer = await person(request, "farmer", boss);
  const factory = await person(request, "factory", boss, "sugarcane_trash");

  const o = await browserFor(browser, factory);
  await o.page.goto("/factory");
  const chip = o.page.getByText(/Live updates paused/);
  await expect(o.page.getByRole("button", { name: /^Notifications/ })).toBeVisible();
  await expect(o.page.locator("html")).toHaveAttribute("data-live", "live"); // the listener is up
  await expect(chip).toBeHidden();

  // block Firestore, and drop the connection the page already holds
  await o.context.route(/127\.0\.0\.1:8080/, (route) => route.abort());
  await o.context.setOffline(true);
  await o.page.waitForTimeout(1_000);
  await o.context.setOffline(false);
  await expect(o.page.locator("html")).toHaveAttribute("data-live", "paused", { timeout: 90_000 });
  await expect(chip).toBeVisible();

  // a change happens while it is paused: the page catches up by itself (every 30 s), with no click and no reload
  await reportLot(request, farmer, "sugarcane_trash");
  await expect(o.page.getByRole("button", { name: "Fund escrow" })).toBeVisible({ timeout: 60_000 });

  // let Firestore back in: live again, and the chip goes away
  await o.context.unroute(/127\.0\.0\.1:8080/);
  await expect(o.page.locator("html")).toHaveAttribute("data-live", "live", { timeout: 90_000 });
  await expect(chip).toBeHidden();

  await retire(request, boss, factory);
  await o.context.close();
});
