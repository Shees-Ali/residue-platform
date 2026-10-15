import { useEffect, useState } from "react";
import { api } from "@/api/client";
import { locationMessage } from "./geo";

export type TrackerStatus = "off" | "starting" | "sharing" | "blocked";

const EVERY_MS = 15_000;

/** While `active`, send the phone's position about every 15 s for this job. Stops when the job is
 * no longer moving or the page closes. A locked screen stops it too: that is a browser limit. */
export function useLocationTracker(jobId: string, active: boolean) {
  const [status, setStatus] = useState<TrackerStatus>("off");
  const [problem, setProblem] = useState("");

  useEffect(() => {
    if (!active || typeof navigator === "undefined" || !navigator.geolocation) {
      setStatus("off");
      return;
    }
    setStatus("starting");
    let lastSent = 0;
    const geo = navigator.geolocation; // keep it: the cleanup must not look it up again
    const watch = geo.watchPosition(
      (p) => {
        setProblem("");
        setStatus("sharing");
        const now = Date.now();
        if (now - lastSent < EVERY_MS) return;
        lastSent = now;
        // a 409 just means the job moved on; nothing to tell the person
        void api
          .POST("/api/jobs/{job_id}/location", {
            params: { path: { job_id: jobId } },
            body: { lat: p.coords.latitude, lon: p.coords.longitude, accuracy_m: p.coords.accuracy },
          })
          .catch(() => {});
      },
      (e) => {
        setStatus(e.code === 1 ? "blocked" : "starting");
        setProblem(locationMessage(e.code));
      },
      { enableHighAccuracy: true, maximumAge: 5_000, timeout: 20_000 },
    );
    return () => geo.clearWatch(watch);
  }, [jobId, active]);

  return { status, problem };
}
