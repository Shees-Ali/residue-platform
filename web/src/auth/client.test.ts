import { auth } from "@/lib/firebase";

// The global setup mocks the API client; load the real middleware.
const real = () => vi.importActual<typeof import("@/api/client")>("@/api/client");
const ctx = (request: Request) => ({ request }) as never;
const setUser = (u: unknown) => ((auth as unknown as { currentUser: unknown }).currentUser = u);

afterEach(() => setUser(null));

test("requests carry the Firebase ID token", async () => {
  setUser({ getIdToken: async () => "tok-123" });
  const { authMiddleware } = await real();
  const out = (await authMiddleware.onRequest!(ctx(new Request("http://t/api/me")))) as Request;
  expect(out.headers.get("Authorization")).toBe("Bearer tok-123");
});

test("signed-out requests carry no token and never an X-Dev-Uid", async () => {
  const { authMiddleware } = await real();
  const out = (await authMiddleware.onRequest!(ctx(new Request("http://t/api/me")))) as Request;
  expect(out.headers.get("Authorization")).toBeNull();
  expect(out.headers.get("X-Dev-Uid")).toBeNull();
});

test("a 401 signs the person out", async () => {
  setUser({ getIdToken: async () => "t" });
  const { authMiddleware } = await real();
  await authMiddleware.onResponse!({ response: new Response(null, { status: 401 }) } as never);
  expect(auth.signOut).toHaveBeenCalled();
});
