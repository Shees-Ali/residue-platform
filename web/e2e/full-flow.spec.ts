import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import {
  JPEG, admin, bell, browserFor, call, expectUnread, must, person, retire, serverUnread, tomorrow, titles,
  type Person,
} from "./support";

// EV7: the whole story in five real browsers. Each person is signed in through the real form. Nothing is
// reloaded after the first load: what they see arrives through the Firestore inbox.
test.describe.serial("a lot from the farmer to settled, in five browsers", () => {
  let boss: Person, farmer: Person, factory: Person, carrier: Person, buyer: Person;
  let adminBefore = 0; // the admin is shared with the other specs, so what they already hold is measured
  const pages: Record<string, Page> = {};
  const contexts: BrowserContext[] = [];

  test.beforeAll(async ({ browser, request }) => {
    boss = await admin(request);
    farmer = await person(request, "farmer", boss);
    factory = await person(request, "factory", boss, "rice_straw");
    carrier = await person(request, "transporter", boss);
    buyer = await person(request, "buyer", boss);
    adminBefore = await serverUnread(request, boss);
    for (const [name, who] of [["admin", boss], ["farmer", farmer], ["factory", factory], ["transporter", carrier], ["buyer", buyer]] as const) {
      const b = await browserFor(browser, who);
      pages[name] = b.page;
      contexts.push(b.context);
    }
    // open each person's own page so their live listener is running before anything happens
    await pages.farmer.goto("/farmer");
    await pages.factory.goto("/factory");
    await pages.transporter.goto("/transporter");
    await pages.admin.goto("/admin");
    await pages.buyer.goto("/market");
    for (const p of Object.values(pages)) await expect(bell(p)).toBeVisible();
    // approval already told the factory and the transporter, and the admin saw both sign up
    await expectUnread(pages.factory, 1);
    await expectUnread(pages.transporter, 1);
    await expectUnread(pages.admin, adminBefore);
  });

  test.afterAll(async ({ request }) => {
    await retire(request, boss, factory, carrier);
    await Promise.all(contexts.map((c) => c.close()));
  });

  test("1. the farmer reports residue; the factory and the admin hear about it live", async () => {
    const farmerPage = pages.farmer;
    await farmerPage.getByRole("button", { name: /Report residue/ }).click();
    const form = farmerPage.getByRole("dialog");
    await form.getByLabel("Residue type").selectOption({ label: "Rice straw" });
    await form.getByLabel(/Quantity/).fill("2.5");
    await form.getByLabel("Pickup date").fill(tomorrow());
    await form.getByLabel("District").selectOption("Lahore");
    await form.getByLabel("Village or area").fill("Raiwind");
    await form.getByRole("button", { name: "Report residue" }).click();
    await expect(form).toBeHidden();

    // no reload anywhere below: these arrive through each person's Firestore inbox
    await expectUnread(pages.factory, 2);
    await expect(pages.factory.getByText(/New lot for you: 2.5 t of rice straw from Raiwind/)).toBeVisible();
    await expect(pages.factory.getByRole("button", { name: "Fund escrow" })).toBeVisible();
    await expect(pages.admin.getByText(/New lot reported/)).toBeVisible();
    await expectUnread(farmerPage, 1); // "Matched to a factory"
  });

  test("2. the factory funds; the transporter is offered the load the moment it happens", async () => {
    await pages.factory.getByRole("button", { name: "Fund escrow" }).click();
    await pages.factory.getByRole("dialog").getByRole("button", { name: /^Fund PKR/ }).click();
    await expect(pages.transporter.getByText(/New load offer/)).toBeVisible();
    await expect(pages.transporter.getByRole("button", { name: "Accept job" })).toBeVisible();
    await expect(pages.farmer.getByText(/Payment secured/)).toBeVisible();
  });

  test("3. the transporter accepts, picks up and delivers with photos and a position", async () => {
    const t = pages.transporter;
    await t.getByRole("button", { name: "Accept job" }).click();
    await expect(t.getByRole("button", { name: "Record pickup" })).toBeVisible();
    await expect(pages.farmer.getByText(/Transporter on the way/)).toBeVisible();

    await t.getByRole("button", { name: "Record pickup" }).click();
    let dialog = t.getByRole("dialog");
    await dialog.getByLabel("Photo of the load").setInputFiles(JPEG);
    await dialog.getByLabel("Weight loaded (kg)").fill("2450");
    await dialog.getByRole("button", { name: "Record pickup" }).click();
    await expect(dialog).toBeHidden({ timeout: 30_000 });
    await expect(pages.factory.getByText(/Load collected/)).toBeVisible();

    await t.getByRole("button", { name: "Record delivery" }).click();
    dialog = t.getByRole("dialog");
    await dialog.getByLabel("Photo of the load").setInputFiles(JPEG);
    await dialog.getByLabel("Weight delivered (kg)").fill("2440");
    await dialog.getByRole("button", { name: "Record delivery" }).click();
    await expect(dialog).toBeHidden({ timeout: 30_000 });
    await expect(pages.factory.getByText(/Load arrived/)).toBeVisible();
    await expect(pages.factory.getByRole("button", { name: "Confirm weight" })).toBeVisible();
  });

  test("4. the factory weighs it; the farmer is asked to confirm, live", async () => {
    await pages.factory.getByRole("button", { name: "Confirm weight" }).click();
    const dialog = pages.factory.getByRole("dialog");
    await dialog.getByLabel("Weight on the weighbridge (kg)").fill("2480");
    await dialog.getByRole("button", { name: "Confirm weight" }).click();
    await expect(dialog).toBeHidden({ timeout: 30_000 });
    await expect(pages.farmer.getByText(/Confirm your payment/)).toBeVisible();
    await expect(pages.farmer.getByRole("button", { name: "Yes, pay me" })).toBeVisible();
    await expect(pages.transporter.getByText(/Delivery confirmed/)).toBeVisible();
  });

  test("5. the farmer confirms; everyone is told it is settled", async () => {
    await pages.farmer.getByRole("button", { name: "Yes, pay me" }).click();
    await expect(pages.farmer.getByText(/You are paid/)).toBeVisible();
    await expect(pages.factory.getByText(/Job settled/)).toBeVisible();
    await expect(pages.admin.getByText(/Job settled/)).toBeVisible();
  });

  test("6. every bell holds the story, in order, and read state follows the person across tabs", async ({ request }) => {
    const farmerTitles = await titles(pages.farmer);
    expect(farmerTitles.reverse()).toEqual([
      "Matched to a factory", "Payment secured", "Transporter on the way", "Picked up", "Delivered",
      "Confirm your payment", "You are paid",
    ]);
    const factoryTitles = (await titles(pages.factory)).reverse();
    expect(factoryTitles).toEqual(["Account approved", "New lot for you", "Transporter assigned", "Load collected", "Load arrived", "Job settled"]);
    expect((await titles(pages.transporter)).reverse()).toEqual(["Account approved", "New load offer", "Delivery confirmed"]);
    const adminTitles = (await titles(pages.admin)).reverse();
    for (const t of ["New factory waiting", "New transporter waiting", "New lot reported", "Escrow funded", "Offer accepted", "Load picked up", "Load delivered", "Weight confirmed", "Job settled"]) {
      expect(adminTitles).toContain(t);
    }
    expect(await titles(pages.buyer).catch(() => [])).toEqual([]); // the buyer has nothing to hear

    // the badge agrees with the server, and marking all read clears it in a second tab of the same person
    const server = await must(request, farmer.token, "GET", "/api/notifications/unread-count");
    expect(server.unread).toBe(7);
    await expectUnread(pages.farmer, 7);
    const second = await pages.farmer.context().newPage();
    await second.goto("/farmer");
    await expectUnread(second, 7);
    await pages.farmer.reload();
    await bell(pages.farmer).click();
    await pages.farmer.getByRole("button", { name: "Mark all read" }).click();
    await expectUnread(pages.farmer, 0);
    await second.reload();
    await expectUnread(second, 0);
    expect((await must(request, farmer.token, "GET", "/api/notifications/unread-count")).unread).toBe(0);
    await second.close();
  });

  test("7. the money adds up and the timeline tells the same story", async ({ request }) => {
    expect((await must(request, boss.token, "GET", "/api/ledger/check")).balanced).toBe(true);
    const jobs = await must(request, boss.token, "GET", "/api/jobs?state=settled");
    const job = jobs[0];
    const timeline = await must(request, boss.token, "GET", `/api/jobs/${job.id}/events`);
    expect(timeline.map((e: { type: string }) => e.type)).toEqual(
      expect.arrayContaining(["lot.created", "lot.matched", "job.funded", "offer.created", "job.accepted", "job.picked_up", "job.delivered", "job.confirmed", "job.settled"]),
    );
    await pages.factory.getByRole("button", { name: /Activity of/ }).first().click();
    await expect(pages.factory.getByRole("dialog").getByText("Settled")).toBeVisible();
    // nothing in the stored text is personal
    const all = await must(request, boss.token, "GET", "/api/notifications?limit=50");
    expect(JSON.stringify(all)).not.toMatch(/\+92\d{9}|@e2e\.test/);
    expect((await call(request, buyer.token, "GET", `/api/jobs/${job.id}/events`)).status).toBe(403);
  });
});
