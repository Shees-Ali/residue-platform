import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

/** A small inline spinner (buttons, table cells). */
export function Spinner({ className }: { className?: string }) {
  return <Loader2 aria-hidden="true" className={cn("animate-spin", className)} />;
}

/** A centred loader for a page or panel while its data is on the way. */
export function PageLoader({ label = "Loading…", fullScreen = false }: { label?: string; fullScreen?: boolean }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex flex-col items-center justify-center gap-3 text-muted-foreground",
        fullScreen ? "min-h-screen" : "py-16",
      )}
    >
      <Spinner className="size-7 text-primary" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

/** A grey placeholder block shaped like the content that will replace it. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-md bg-muted", className)} />;
}
