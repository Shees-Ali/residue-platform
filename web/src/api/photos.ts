import { auth } from "@/lib/firebase";
import { validatePhotoFile } from "@/lib/validation";
import { api } from "./client";
import { errorMessage } from "./errors";
import { ApiError, unwrap } from "./query";

export type PhotoKind = "pickup" | "delivery" | "weighbridge";

/** A photo problem the person can fix (wrong type, too big, upload failed). */
export class PhotoError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PhotoError";
  }
}

/** Upload one photo for a job and return the path to send with the pickup, delivery or grade.
 * Checks the file first, asks the API for an upload address, then PUTs the file to it. */
export async function uploadPhoto(jobId: string, kind: PhotoKind, file: File): Promise<string> {
  const bad = validatePhotoFile(file);
  if (bad) throw new PhotoError(bad);
  const slot = await unwrap(
    api.POST("/api/jobs/{job_id}/photos/upload-url", {
      params: { path: { job_id: jobId } },
      body: { kind, content_type: file.type as "image/jpeg" | "image/png" | "image/webp" },
    }),
  );
  const local = slot.upload_url.startsWith("/"); // the dev store lives behind our own API
  const headers: Record<string, string> = { "Content-Type": file.type };
  if (local) {
    const token = await auth.currentUser?.getIdToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const base = local ? (import.meta.env.VITE_API_BASE_URL ?? "") : "";
  let res: Response;
  try {
    res = await fetch(`${base}${slot.upload_url}`, { method: "PUT", headers, body: file });
  } catch {
    throw new PhotoError("The photo could not be uploaded. Check your connection and try again.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => undefined);
    throw new ApiError(errorMessage(body, "The photo could not be uploaded."), res.status);
  }
  return slot.path;
}
