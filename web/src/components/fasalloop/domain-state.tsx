import { createContext, useContext, useEffect, useReducer, useState, type ReactNode, type Dispatch } from "react";
import { reducer, type DomainAction, type DomainState } from "@/lib/domain/engine";
import { seedDomain } from "@/lib/domain/seed";

// React binding for the pure engine. The reducer lives in lib/domain/engine.ts
// (no React, fully tested); this layer only holds state, persists it, and
// exposes the dispatch. It persists under its own key (residue-demo-v2) so the
// Phase 0 demo screens (demo-state.tsx, residue-demo-v1) stay untouched until
// Phase 2 migrates them onto this model.

const STORAGE_KEY = "residue-demo-v2";

interface DomainContextValue {
  state: DomainState;
  dispatch: Dispatch<DomainAction>;
  ready: boolean;
}

const DomainContext = createContext<DomainContextValue | null>(null);

export function DomainProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, seedDomain);
  const [ready, setReady] = useState(false);

  // Hydrate once on mount; the seed is the fallback when nothing is stored or
  // the stored shape is stale/corrupt.
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed && Array.isArray(parsed.jobs) && Array.isArray(parsed.ledger)) {
          dispatch({ type: "reset", next: parsed as DomainState });
        }
      }
    } catch {
      // fall through to the seed
    }
    setReady(true);
  }, []);

  // Write-through on every change once hydrated.
  useEffect(() => {
    if (!ready) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // quota or private mode — the demo still runs in-memory
    }
  }, [state, ready]);

  return (
    <DomainContext.Provider value={{ state, dispatch, ready }}>
      {children}
    </DomainContext.Provider>
  );
}

export function useDomain(): DomainContextValue {
  const value = useContext(DomainContext);
  if (!value) throw new Error("DomainProvider required");
  return value;
}
