import { expect, test } from "@playwright/test";
import { admin, bell, browserFor, driveToConfirmed, expectUnread, person, reportLot, retire, titles } from "./support";

// EV2/F4: a dispute reaches the admin as a warning, the factory as a hold, and the farmer as a receipt.
test("a disputed payment alerts the admin, the factory and the farmer, and resolving it tells the farmer", async ({ browser, request }) => {
  const boss = await admin(request);
  const farmer = await person(request, "farmer", boss);
  const factory = await person(request, "factory", boss, "wheat_straw");
  const carrier = await person(request, "transporter", boss);
  const jobId = await reportLot(request, farmer, "wheat_straw");

  const f = await browserFor(browser, farmer);
  const o = await browserFor(browser, factory);
  const a = await browserFor(browser, boss);
  await f.page.goto("/farmer");
  await o.page.goto("/factory");
  await a.page.goto("/admin");
  await expect(bell(a.page)).toBeVisible();

  await driveToConfirmed(request, { factory, transporter: carrier, jobId, weightKg: 1200 });
  await expect(f.page.getByRole("button", { name: "Dispute" })).toBeVisible();

  await f.page.getByRole("button", { name: "Dispute" }).click();
  const dialog = f.page.getByRole("dialog");
  await dialog.getByLabel("What is wrong?").fill("The weight is far too low");
  await dialog.getByRole("button", { name: /Send dispute|Dispute/ }).last().click();

  // the admin gets a warning toast (an alert), and the dispute is in the queue without a reload
  await expect(a.page.getByRole("alert").filter({ hasText: "Farmer disputed a payment" })).toBeVisible();
  await expect(a.page.getByText(/far too low/)).toBeVisible(); // the queue shows what the farmer wrote...
  await expect(o.page.getByText(/Payment on hold/)).toBeVisible();
  await expectUnread(f.page, (await titles(f.page)).length); // ...but a notification never repeats it
  const adminList = await titles(a.page);
  expect(adminList).toContain("Farmer disputed a payment");
  const bellText = await a.page.evaluate(() => document.body.innerText);
  expect(bellText).not.toContain("The weight is far too low\n\nFarmer disputed");

  // resolving it tells the farmer
  await a.page.getByRole("button", { name: /Resolve/ }).first().click();
  await expect(f.page.getByText(/Dispute reviewed/)).toBeVisible();

  await retire(request, boss, factory, carrier);
  await Promise.all([f.context.close(), o.context.close(), a.context.close()]);
});
