import { useState, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { useToast } from "@/components/ui/toast";
import { createQueryClient } from "./query";

/** Server-state cache for the whole app. Must sit inside ToastProvider. */
export function QueryProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const [client] = useState(() => createQueryClient(toast.error));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
