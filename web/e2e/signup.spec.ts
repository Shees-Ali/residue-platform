import { expect, test } from "@playwright/test";
import { email, ensureAccount, must, signInThroughTheForm, PASSWORD } from "./support";

// Signing in again after a signup that stopped at step 2 resumes at step 2 (the bug that made a
// half-finished account impossible to finish), and the farmer's phone is optional.
test("a half-finished signup resumes at step 2 on every sign-in, and the farmer finishes without a phone", async ({ browser, request }) => {
  const mail = email("resume");
  const { token } = await ensureAccount(request, mail); // step 1 happened; step 2 never did

  const context = await browser.newContext({ baseURL: "http://127.0.0.1:5183" });
  const page = await context.newPage();
  await signInThroughTheForm(page, mail);
  await expect(page.getByRole("heading", { name: "How will you use it?" })).toBeVisible();

  // reload: the session is remembered and step 2 is still where they are
  await page.reload();
  await expect(page.getByRole("heading", { name: "How will you use it?" })).toBeVisible();

  // sign out and sign in again with the same account: back to step 2, not stuck on the sign-in page
  await page.getByRole("button", { name: "Use a different account" }).click();
  await expect(page.getByRole("heading", { name: "Create your account" })).toBeVisible();
  await page.goto("/login");
  await page.getByLabel("Email").fill(mail);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "How will you use it?" })).toBeVisible({ timeout: 30_000 });

  // a farmer: name filled in, phone optional and left empty
  await page.getByRole("radio", { name: /Farmer/ }).click();
  await expect(page.getByLabel("Phone (optional)")).toBeVisible();
  await page.getByLabel("Your name").fill("Asma Bibi");
  await page.getByRole("button", { name: "Finish" }).click();
  await expect(page).toHaveURL(/\/farmer/, { timeout: 30_000 });
  await expect(page.getByRole("button", { name: /Report residue/ })).toBeVisible();

  const me = await must(request, token, "GET", "/api/me");
  expect(me).toMatchObject({ role: "farmer", status: "active", display_name: "Asma Bibi", phone: null });
  await context.close();
});
