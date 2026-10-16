import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { X } from "lucide-react";

type Kind = "error" | "info" | "warning";
interface ToastItem {
  id: number;
  kind: Kind;
  message: string;
}
interface ToastApi {
  error: (message: string) => void;
  info: (message: string) => void;
  /** Needs attention but is not a failure: a dispute, an unbalanced ledger. */
  warn: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);
const SHOW_MS = 7000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);

  const dismiss = useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), []);
  const push = useCallback(
    (kind: Kind, message: string) => {
      const id = next.current++;
      // The same message twice in a row is one toast, not a stack.
      setItems((all) => [...all.filter((t) => t.message !== message), { id, kind, message }].slice(-4));
      setTimeout(() => dismiss(id), SHOW_MS);
    },
    [dismiss],
  );
  const api = useMemo<ToastApi>(
    () => ({ error: (m) => push("error", m), info: (m) => push("info", m), warn: (m) => push("warning", m) }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`} role={t.kind === "info" ? "status" : "alert"}>
            <span>{t.message}</span>
            <button type="button" aria-label="Dismiss" onClick={() => dismiss(t.id)}>
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

const silent: ToastApi = { error: () => {}, info: () => {}, warn: () => {} };

/** Show a toast. Outside a ToastProvider it does nothing, so small components stay testable. */
export function useToast(): ToastApi {
  return useContext(ToastContext) ?? silent;
}
