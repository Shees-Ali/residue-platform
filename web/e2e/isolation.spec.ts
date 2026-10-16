import { expect, test } from "@playwright/test";
import { FIRESTORE, PROJECT, admin, bell, browserFor, call, driveToConfirmed, expectUnread, person, reportLot, retire, titles } from "./support";

// EV5: you hear only what is yours, in the screens and in Firestore itself.
test("a second farmer sees none of the first farmer's notifications, and Firestore refuses to show them", async ({ browser, request }) => {
  const boss = await admin(request);
  const farmerA = await person(request, "farmer", boss);
  const farmerB = await person(request, "farmer", boss);
  const factory = await person(request, "factory", boss, "cotton_stalk");
  const carrier = await person(request, "transporter", boss);

  const a = await browserFor(browser, farmerA);
  const b = await browserFor(browser, farmerB);
  await a.page.goto("/farmer");
  await b.page.goto("/farmer");

  const jobId = await reportLot(request, farmerA, "cotton_stalk");
  await driveToConfirmed(request, { factory, transporter: carrier, jobId });
  // matched, payment secured, accepted, picked up, delivered, confirm your payment: all arrived live
  await expectUnread(a.page, 6);
  expect(await titles(a.page)).toHaveLength(6);

  // farmer B's bell is empty, and stays empty
  await expect(bell(b.page)).toHaveAttribute("aria-label", "Notifications");
  await b.page.getByRole("button", { name: "Notifications" }).click();
  await expect(b.page.getByText("No notifications yet")).toBeVisible();

  // Firestore itself, asked directly with B's own token: A's inbox is closed, B's own is open
  const path = (uid: string) => `${FIRESTORE}/v1/projects/${PROJECT}/databases/(default)/documents/users/${uid}/inbox`;
  const asA = await request.get(path(farmerA.uid), { headers: { Authorization: `Bearer ${farmerA.token}` } });
  expect(asA.status()).toBe(200);
  expect((await asA.json()).documents.length).toBeGreaterThan(0);
  const asB = await request.get(path(farmerA.uid), { headers: { Authorization: `Bearer ${farmerB.token}` } });
  expect(asB.status()).toBe(403);
  const nobody = await request.get(path(farmerA.uid));
  expect(nobody.status()).toBe(403);
  const write = await request.post(path(farmerB.uid), {
    headers: { Authorization: `Bearer ${farmerB.token}` },
    data: { fields: { title: { stringValue: "forged" } } },
  });
  expect(write.status()).toBe(403); // nobody writes from a client, not even into their own inbox

  // and the API agrees: B cannot read A's notifications or events
  expect((await call(request, farmerB.token, "GET", `/api/jobs/${jobId}/events`)).status).toBe(404);

  await retire(request, boss, factory, carrier);
  await a.context.close();
  await b.context.close();
});
