import { useState } from "react";
import { History } from "lucide-react";
import { useJobEvents } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/spinner";

const WHEN = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** A button that opens what happened to a job and who did it (EV1). */
export function JobActivityButton({ jobId, title }: { jobId: string; title: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)} aria-label={`Activity of ${title}`}>
        <History />
        Activity
      </Button>
      {open && <ActivityDialog jobId={jobId} title={title} onClose={() => setOpen(false)} />}
    </>
  );
}

function ActivityDialog({ jobId, title, onClose }: { jobId: string; title: string; onClose: () => void }) {
  const events = useJobEvents(jobId, true);
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Activity</DialogTitle>
        <DialogDescription>{title}</DialogDescription>
        {events.isPending ? (
          <div aria-busy="true" className="auth-stack">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : events.isError ? (
          <Button variant="outline" loading={events.isFetching} onClick={() => void events.refetch()}>
            Try again
          </Button>
        ) : events.data.length === 0 ? (
          <div className="empty-state">Nothing has happened yet.</div>
        ) : (
          <ol className="activity-list">
            {events.data.map((e) => (
              <li key={e.id}>
                <span className="activity-summary">{e.summary}</span>
                <span className="activity-meta">
                  {e.actor_role ? `${e.actor_role} · ` : ""}
                  {WHEN.format(new Date(e.created_at))}
                </span>
              </li>
            ))}
          </ol>
        )}
      </DialogContent>
    </Dialog>
  );
}
