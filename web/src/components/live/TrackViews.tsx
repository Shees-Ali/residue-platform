import { useState } from "react";
import { MapPin } from "lucide-react";
import { useActiveTracks, useTrack } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/spinner";
import { arrivalText, offSiteNotes } from "@/lib/tracking";
import { QueryBoundary, SectionHead, STATE_LABEL } from "./common";
import { JobMap } from "./JobMap";

/** The map and the words for one job, loading its track. */
export function TrackBody({ jobId }: { jobId: string }) {
  const q = useTrack(jobId);
  if (q.isPending) return <Skeleton className="h-64" />;
  if (q.isError) {
    return (
      <Button variant="outline" onClick={() => void q.refetch()}>
        Try again
      </Button>
    );
  }
  const t = q.data;
  const notes = offSiteNotes(t);
  return (
    <div className="auth-stack">
      <JobMap pickup={t.pickup} factory={t.factory} path={t.points} truck={t.last} />
      <p className="text-sm">{arrivalText(t)}</p>
      {notes.map((n) => (
        <span key={n} className="chip warn">
          {n}
        </span>
      ))}
    </div>
  );
}

/** Factory: follow one load. */
export function TrackDialog({ jobId, title, onClose }: { jobId: string; title: string; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Track this load</DialogTitle>
        <DialogDescription>{title}</DialogDescription>
        <TrackBody jobId={jobId} />
        <div className="flex justify-end">
          <Button onClick={onClose}>Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Admin: every load on the move, pick one to see it on the map. */
export function LiveMap() {
  const active = useActiveTracks();
  const [picked, setPicked] = useState<string | null>(null);
  return (
    <section aria-label="Live map" className="mb-8">
      <SectionHead title="Live map" />
      <QueryBoundary q={active} what="the loads on the move">
        {(rows) => {
          const chosen = rows.find((r) => r.job_id === picked) ?? rows[0];
          return rows.length === 0 ? (
            <div className="empty-state">No load is on the road right now.</div>
          ) : (
            <div className="auth-stack">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Load</th>
                      <th>Stage</th>
                      <th>Position</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.job_id} aria-selected={r.job_id === chosen?.job_id}>
                        <td className="font-medium">
                          {r.quantity_tonnes} t {r.residue_type}
                          <span className="table-sub">
                            {r.village} to {r.factory_name}
                          </span>
                        </td>
                        <td>{STATE_LABEL[r.state] ?? r.state}</td>
                        <td>{arrivalText(r)}</td>
                        <td>
                          <Button size="sm" variant="ghost" onClick={() => setPicked(r.job_id)}>
                            <MapPin />
                            Show
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {chosen && <TrackBody jobId={chosen.job_id} />}
            </div>
          );
        }}
      </QueryBoundary>
    </section>
  );
}
