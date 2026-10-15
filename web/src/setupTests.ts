import "@testing-library/jest-dom/vitest";

// jsdom lacks matchMedia and scrollIntoView (used by the marketplace hero and mobile CSS).
if (!window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}

// No test talks to Firebase or the network. Individual tests override the API mocks.
vi.mock("@/lib/firebase", () => ({
  auth: { currentUser: null, signOut: vi.fn() },
  googleProvider: {},
  db: {},
}));
vi.mock("@/api/client", () => ({
  api: {
    GET: vi.fn(async () => ({ data: [], response: { status: 200 } })),
    POST: vi.fn(async () => ({ error: { detail: "not mocked" }, response: { status: 400 } })),
  },
}));
