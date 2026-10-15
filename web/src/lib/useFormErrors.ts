import { useEffect, useRef, useState } from "react";
import type { Errors } from "./validation";

/** Per-field errors for a form: set them all on submit (focusing the first bad field), clear one
 * as the person edits it. Attach `ref` to the <form>. */
export function useFormErrors() {
  const ref = useRef<HTMLFormElement>(null);
  const [errors, setErrors] = useState<Errors>({});
  const [focusTick, setFocusTick] = useState(0);

  useEffect(() => {
    if (focusTick) ref.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }, [focusTick]);

  return {
    ref,
    errors,
    fail: (next: Errors) => {
      setErrors(next);
      setFocusTick((t) => t + 1);
    },
    clear: (field: string) =>
      setErrors((all) => {
        if (!(field in all)) return all;
        const { [field]: _gone, ...rest } = all;
        return rest;
      }),
    set: (field: string, message: string | undefined) =>
      setErrors((all) => {
        const { [field]: _old, ...rest } = all;
        return message ? { ...rest, [field]: message } : rest;
      }),
    reset: () => setErrors({}),
  };
}
