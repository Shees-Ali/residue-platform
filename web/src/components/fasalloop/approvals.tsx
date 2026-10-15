import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { api } from "@/api/client";
import { unwrap } from "@/api/query";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/spinner";

type UserRow = components["schemas"]["UserOut"];

const PENDING_KEY = ["users", "pending"] as const;

function describe(u: UserRow): string {
  const d = u.details as Record<string, unknown>;
  if (u.role === "factory") {
    const price = typeof d.price_per_tonne === "number" ? ` · PKR ${(d.price_per_tonne / 100).toLocaleString()}/t` : "";
    return `${String(d.name ?? "")}${price} · ${(d.residues as string[] | undefined)?.join(", ") ?? ""}`;
  }
  if (u.role === "transporter") return `${String(d.phone ?? "")}`;
  return "";
}

/** Accounts waiting for an admin: transporters (pick a tier) and factories. Real API data.
 * Loading, errors (toasted centrally) and refetching after a decision are handled by Query. */
export function PendingApprovals() {
  const qc = useQueryClient();
  const [tiers, setTiers] = useState<Record<string, number>>({});

  const pending = useQuery({
    queryKey: PENDING_KEY,
    queryFn: () => unwrap(api.GET("/api/users", { params: { query: { status: "pending" } } })),
  });

  const decide = useMutation({
    mutationFn: ({ uid, action }: { uid: string; action: "approve" | "reject" }) => {
      const params = { path: { uid } };
      return action === "approve"
        ? unwrap(api.POST("/api/users/{uid}/approve", { params, body: { tier: tiers[uid] ?? 1 } }))
        : unwrap(api.POST("/api/users/{uid}/reject", { params }));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
  const working = (uid: string) => decide.isPending && decide.variables?.uid === uid;

  if (pending.isPending) {
    return (
      <section aria-label="Pending approvals" aria-busy="true" className="mb-6">
        <Skeleton className="mb-3 h-5 w-56" />
        <Skeleton className="h-24 w-full" />
      </section>
    );
  }
  if (pending.isError) {
    return (
      <section aria-label="Pending approvals" className="mb-6 flex items-center gap-3 text-sm">
        <span className="text-muted-foreground">Could not load accounts waiting for approval.</span>
        <Button size="sm" variant="outline" loading={pending.isFetching} onClick={() => void pending.refetch()}>
          Try again
        </Button>
      </section>
    );
  }
  const rows = pending.data;
  if (!rows.length) return null;

  return (
    <section aria-label="Pending approvals" className="mb-6">
      <div className="section-title">
        <h2>Waiting for approval ({rows.length})</h2>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Email</th>
              <th>Details</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.uid}>
                <td className="font-medium">{u.display_name || "Unnamed"}</td>
                <td className="capitalize">{u.role}</td>
                <td>{u.email ?? "—"}</td>
                <td>{describe(u)}</td>
                <td>
                  <div className="flex items-center justify-end gap-2">
                    {u.role === "transporter" && (
                      <select
                        className="compact-select"
                        aria-label={`Tier for ${u.display_name}`}
                        value={tiers[u.uid] ?? 1}
                        onChange={(e) => setTiers({ ...tiers, [u.uid]: Number(e.target.value) })}
                      >
                        <option value={1}>Tier 1 · up to 3 t</option>
                        <option value={2}>Tier 2 · up to 7 t</option>
                        <option value={3}>Tier 3 · up to 15 t</option>
                      </select>
                    )}
                    <Button
                      size="sm"
                      loading={working(u.uid) && decide.variables?.action === "approve"}
                      disabled={working(u.uid)}
                      onClick={() => decide.mutate({ uid: u.uid, action: "approve" })}
                    >
                      <Check size={14} /> Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      loading={working(u.uid) && decide.variables?.action === "reject"}
                      disabled={working(u.uid)}
                      onClick={() => decide.mutate({ uid: u.uid, action: "reject" })}
                    >
                      <X size={14} /> Reject
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
