import { api } from "@/api/client";
import { quiet } from "./defaults";

export type Rows = Record<string, unknown>;

/** Answer GET requests by path; anything not listed is an empty list. A value shaped
 * `{error, response}` is returned as a failed call; a function is called with the request. */
export function mockGet(rows: Rows) {
  vi.mocked(api.GET).mockImplementation((async (path: string, init?: unknown) => {
    let hit = rows[path];
    if (typeof hit === "function") hit = await (hit as (init?: unknown) => unknown)(init);
    if (hit instanceof Error) throw hit;
    return hit && typeof hit === "object" && "error" in (hit as object)
      ? hit
      : { data: hit ?? quiet(path), response: { status: 200 } };
  }) as never);
}

/** The POST calls made to a path, as [path, init] pairs. */
export const posted = (path: string) =>
  vi.mocked(api.POST).mock.calls.filter((c) => c[0] === path) as unknown as [
    string,
    { body?: Record<string, unknown>; params?: { path?: Record<string, string>; header?: Record<string, string> } },
  ][];

export const ok = (data: unknown, status = 200) => ({ data, response: { status } }) as never;
export const fail = (detail: string, status: number, errors?: unknown) =>
  ({ error: { detail, ...(errors ? { errors } : {}) }, response: { status } }) as never;
