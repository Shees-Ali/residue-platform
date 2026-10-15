import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { errorMessage, fieldErrorsOf } from "./errors";

/** A failed API call. `message` is already readable, so it can go straight into a toast. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    /** {field: message} when the API says which inputs were wrong. */
    public fields: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ApiResult<T> {
  data?: T;
  error?: unknown;
  response: { status: number };
}

/** An ApiError from a failed response body. */
export function apiErrorFrom(error: unknown, status: number): ApiError {
  return new ApiError(errorMessage(error), status, fieldErrorsOf(error));
}

/** Turn an openapi-fetch result into data, or throw an ApiError. Use it inside query and mutation
 * functions: `queryFn: () => unwrap(api.GET("/api/users"))`. */
export async function unwrap<T>(call: Promise<ApiResult<T>>): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined || data === undefined) {
    throw apiErrorFrom(error, response.status);
  }
  return data;
}

declare module "@tanstack/react-query" {
  interface Register {
    queryMeta: { silent?: boolean };
    mutationMeta: { silent?: boolean };
  }
}

/** One client for the app. Every failed query or mutation raises a toast through `onError`, unless
 * it opts out with `meta: { silent: true }`, so screens do not each write their own error handling. */
export function createQueryClient(onError: (message: string) => void): QueryClient {
  const say = (e: unknown) =>
    onError(e instanceof Error && e.message ? e.message : "Something went wrong. Try again.");
  return new QueryClient({
    queryCache: new QueryCache({ onError: (e, q) => !q.meta?.silent && say(e) }),
    mutationCache: new MutationCache({ onError: (e, _v, _c, m) => !m.meta?.silent && say(e) }),
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false,
        // Retry a flaky network once; never retry a refusal (401, 403, 404, 409, 422).
        retry: (count, e) => count < 1 && !(e instanceof ApiError && e.status < 500),
      },
    },
  });
}
