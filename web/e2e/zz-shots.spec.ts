import { test } from "@playwright/test";
import { admin, browserFor, driveToConfirmed, must, person, reportLot } from "./support";

test("screenshots of the admin page", async ({ browser, request }) => {
  test.setTimeout(180_000);
  const boss = await admin(request);
  const farmer = await person(request, "farmer", boss);
  const factory = await person(request, "factory", boss, "rice_straw");
  const carrier = await person(request, "transporter", boss);
  await person(request, "buyer", boss);
  const settled = await reportLot(request, farmer);
  await driveToConfirmed(request, { factory, transporter: carrier, jobId: settled });
  await must(request, farmer.token, "POST", `/api/jobs/${settled}/verify`, { confirmed: true, note: "" });
  const open = await reportLot(request, farmer);
  await must(request, factory.token, "POST", `/api/jobs/${open}/fund`);
  await reportLot(request, farmer);
  const a = await browserFor(browser, boss);
  for (const [name, w, h] of [["desktop", 1440, 900], ["mobile", 390, 844]] as const) {
    await a.page.setViewportSize({ width: w, height: h });
    await a.page.goto("/admin");
    await a.page.waitForTimeout(2500);
    await a.page.screenshot({ path: `shots/admin-${name}.png`, fullPage: true });
  }
  await a.page.setViewportSize({ width: 1440, height: 900 });
  for (const path of ["/transporter", "/farmer", "/factory", "/market"]) {
    await a.page.goto(path);
    await a.page.waitForTimeout(2000);
    await a.page.screenshot({ path: `shots/admin-at${path.replace("/", "-")}.png`, fullPage: false });
  }
  await a.context.close();
});
