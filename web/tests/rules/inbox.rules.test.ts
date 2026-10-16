import { readFileSync } from "node:fs";
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment,
} from "@firebase/rules-unit-testing";
import {
  addDoc,
  collection,
  collectionGroup,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  limit,
  orderBy,
  query,
  setDoc,
  updateDoc,
} from "firebase/firestore";

// EV5: only the owner reads their inbox, nobody writes from a client, everything else is closed.
let env: RulesTestEnvironment;
const sample = {
  type: "job.funded", level: "info", title: "Payment secured", body: "Funded.",
  job_id: null, refresh: ["jobs"], created_at: new Date(), expires_at: new Date(),
};

beforeAll(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-residue",
    firestore: {
      rules: readFileSync(new URL("../../../deploy/firestore.rules", import.meta.url), "utf8"),
      host: "127.0.0.1",
      port: 8080,
    },
  });
});
afterAll(async () => env.cleanup());
beforeEach(async () => {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async (ctx) => {
    // what the API (a service account) wrote; `firestore()` once per context
    const db = ctx.firestore();
    await setDoc(doc(db, "users/alice/inbox/n1"), sample);
    await setDoc(doc(db, "users/bob/inbox/n2"), sample);
    await setDoc(doc(db, "events/old"), { type: "job.updated" });
  });
});

const as = (uid: string) => env.authenticatedContext(uid).firestore();
const anon = () => env.unauthenticatedContext().firestore();

describe("reading", () => {
  test("a person reads their own notification", async () => {
    await assertSucceeds(getDoc(doc(as("alice"), "users/alice/inbox/n1")));
  });

  test("a person lists their own inbox, newest first, the way the app does", async () => {
    const q = query(collection(as("alice"), "users/alice/inbox"), orderBy("created_at", "desc"), limit(20));
    const snap = await assertSucceeds(getDocs(q));
    expect(snap.docs.map((d) => d.id)).toEqual(["n1"]);
  });

  test("nobody reads another person's notification or inbox", async () => {
    await assertFails(getDoc(doc(as("bob"), "users/alice/inbox/n1")));
    await assertFails(getDocs(collection(as("bob"), "users/alice/inbox")));
  });

  test("a signed-out visitor reads nothing", async () => {
    await assertFails(getDoc(doc(anon(), "users/alice/inbox/n1")));
    await assertFails(getDocs(collection(anon(), "users/alice/inbox")));
  });

  test("a collection-group query cannot be used to read other people's inboxes", async () => {
    await assertFails(getDocs(collectionGroup(as("bob"), "inbox")));
  });
});

describe("writing", () => {
  test("a person cannot create, change or delete their own notifications", async () => {
    const db = as("alice");
    await assertFails(setDoc(doc(db, "users/alice/inbox/new"), sample));
    await assertFails(addDoc(collection(db, "users/alice/inbox"), sample));
    await assertFails(updateDoc(doc(db, "users/alice/inbox/n1"), { read: true }));
    await assertFails(deleteDoc(doc(db, "users/alice/inbox/n1")));
  });

  test("nobody writes into someone else's inbox, signed in or not", async () => {
    await assertFails(setDoc(doc(as("bob"), "users/alice/inbox/forged"), sample));
    await assertFails(setDoc(doc(anon(), "users/alice/inbox/forged"), sample));
  });
});

describe("everything else is closed", () => {
  test("the old global events collection is gone for readers and writers", async () => {
    await assertFails(getDoc(doc(as("alice"), "events/old")));
    await assertFails(getDocs(collection(as("alice"), "events")));
    await assertFails(addDoc(collection(as("alice"), "events"), { type: "job.updated" }));
  });

  test("a person's own user document and any other collection are closed too", async () => {
    await assertFails(getDoc(doc(as("alice"), "users/alice")));
    await assertFails(setDoc(doc(as("alice"), "users/alice"), { role: "admin" }));
    await assertFails(getDoc(doc(as("alice"), "anything/else")));
    await assertFails(setDoc(doc(as("alice"), "anything/else"), { a: 1 }));
  });
});
