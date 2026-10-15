import { useRef, useState } from "react";
import { firebaseMessage } from "./AuthProvider";
import { useToast } from "@/components/ui/toast";

/** Run a sign-in action. `busy` is true exactly while the action is in flight: it clears only when
 * the action settles (success or error) or when the person presses Cancel. Errors always toast.
 *
 * Nothing here guesses that a request has finished. A Google popup that the browser never reports
 * as closed keeps `busy` true; the page offers a Cancel button so the person decides. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const current = useRef(0); // which run owns `busy`; a cancelled or replaced run cannot clear it
  const toast = useToast();

  async function run(action: () => Promise<void>) {
    const id = ++current.current;
    setBusy(true);
    try {
      await action();
    } catch (e) {
      if (id === current.current) {
        const message = firebaseMessage(e);
        if (message) toast.error(message);
      }
    } finally {
      if (id === current.current) setBusy(false);
    }
  }

  /** Stop waiting. A late result from the cancelled action is ignored by this hook. */
  function cancel() {
    current.current++;
    setBusy(false);
  }

  return { busy, run, cancel };
}
