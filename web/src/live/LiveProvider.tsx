import { useEffect, useRef, useState, type ReactNode } from "react";
import { collection, limit, onSnapshot, orderBy, query } from "firebase/firestore";
import { useQueryClient } from "@tanstack/react-query";
import { NOTIFICATIONS_KEY } from "@/api/hooks";
import { useAuth } from "@/auth/AuthProvider";
import { useToast } from "@/components/ui/toast";
import { db } from "@/lib/firebase";
import { LiveContext, type LiveStatus } from "./status";

const RETRY_MS = 15_000;

interface InboxDoc {
  title?: string;
  body?: string;
  level?: string;
  refresh?: string[];
}

/** Listens to the signed-in person's own Firestore inbox (EV3). A new doc means something changed:
 * toast it, and refetch the screens it names. The first snapshot only catches up, silently. */
export function LiveProvider({ children }: { children: ReactNode }) {
  const { user, refresh } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState<LiveStatus>("off");
  const uid = user?.uid;
  const enabled = Boolean(user?.live_updates);
  const latest = useRef({ refresh, toast });
  latest.current = { refresh, toast };

  // handy for the browser tests and for anyone inspecting the page: <html data-live="live">
  useEffect(() => {
    document.documentElement.dataset.live = status;
  }, [status]);

  useEffect(() => {
    if (!uid || !enabled) {
      setStatus("off");
      return;
    }
    setStatus("connecting");
    const seen = new Set<string>();
    let seeded = false;
    let unsubscribe = () => {};
    let retry: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    function announce(d: InboxDoc) {
      const text = [d.title, d.body].filter(Boolean).join(": ");
      if (text) (d.level === "warning" ? latest.current.toast.warn : latest.current.toast.info)(text);
      for (const root of d.refresh ?? []) {
        if (root === "me") void latest.current.refresh();
        else void qc.invalidateQueries({ queryKey: [root] });
      }
      void qc.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    }

    function start() {
      const inbox = query(collection(db, "users", uid!, "inbox"), orderBy("created_at", "desc"), limit(20));
      unsubscribe = onSnapshot(
        inbox,
        { includeMetadataChanges: true },
        (snap) => {
          if (snap.metadata.fromCache) {
            setStatus(seeded ? "paused" : "connecting"); // offline: the cache answers, nothing is live
            return;
          }
          setStatus("live");
          if (!seeded) {
            seeded = true;
            snap.docs.forEach((d) => seen.add(d.id));
            void qc.invalidateQueries(); // catch up on whatever happened while we were not listening
            return;
          }
          for (const change of snap.docChanges()) {
            if (change.type !== "added" || seen.has(change.doc.id)) continue;
            seen.add(change.doc.id);
            announce(change.doc.data() as InboxDoc);
          }
        },
        () => {
          if (stopped) return;
          setStatus("paused");
          retry = setTimeout(start, RETRY_MS); // a failed listener is over: start another
        },
      );
    }
    start();
    return () => {
      stopped = true;
      unsubscribe();
      if (retry) clearTimeout(retry);
    };
  }, [uid, enabled, qc]);

  return <LiveContext.Provider value={status}>{children}</LiveContext.Provider>;
}
