/** A readable message from any API error body (FastAPI detail string, {code, message}, a list of
 * validation problems, or the agent-style {error, message}). */
export function errorMessage(error: unknown, fallback = "Something went wrong. Try again."): string {
  if (!error || typeof error !== "object") return fallback;
  const body = error as { detail?: unknown; message?: unknown };
  const detail = body.detail ?? body;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
      .filter(Boolean);
    return msgs.length ? msgs.join("; ") : fallback;
  }
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return typeof body.message === "string" ? body.message : fallback;
}

/** {field: message} from the API's `errors` list ({detail, errors:[{field, message, code}]}). */
export function fieldErrorsOf(error: unknown): Record<string, string> {
  const list = error && typeof error === "object" ? (error as { errors?: unknown }).errors : undefined;
  const out: Record<string, string> = {};
  if (Array.isArray(list)) {
    for (const e of list) {
      if (e && typeof e === "object" && "field" in e && "message" in e) {
        const { field, message } = e as { field: unknown; message: unknown };
        if (field && !(String(field) in out)) out[String(field)] = String(message);
      }
    }
  }
  return out;
}
