import { useState, type FormEvent } from "react";
import { Pencil, Search } from "lucide-react";
import { useUserProfile, useUsers, type UserFilter } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { LIMITS } from "@/lib/validation";
import { QueryBoundary, SectionHead } from "./common";
import { ProfileForm } from "./ProfileForm";

const ROLES = ["farmer", "buyer", "transporter", "factory", "admin"] as const;
const STATUSES = ["active", "pending", "suspended"] as const;

/** Admin: find anyone and edit their details (a transporter's tier and max load included). */
export function AdminPeople() {
  const [filter, setFilter] = useState<UserFilter>({});
  const [text, setText] = useState("");
  const [problem, setProblem] = useState<string>();
  const [editing, setEditing] = useState<string | null>(null);
  const users = useUsers(filter);

  function search(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    const bad = t.length > LIMITS.search.max ? `Search must be at most ${LIMITS.search.max} characters` : undefined;
    setProblem(bad);
    if (!bad) setFilter((f) => ({ ...f, q: t || undefined }));
  }

  return (
    <section aria-label="People" className="mb-8">
      <SectionHead title="People" />
      <form className="flex flex-wrap items-end gap-3 mb-3" onSubmit={search} noValidate>
        <Field label="Search by name or email" error={problem}>
          <input
            value={text}
            maxLength={LIMITS.search.max}
            onChange={(e) => {
              setText(e.target.value);
              setProblem(undefined);
            }}
          />
        </Field>
        <Field label="Role">
          <select
            value={filter.role ?? ""}
            onChange={(e) => setFilter((f) => ({ ...f, role: (e.target.value || undefined) as UserFilter["role"] }))}
          >
            <option value="">All roles</option>
            {ROLES.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </Field>
        <Field label="Status">
          <select
            value={filter.status ?? ""}
            onChange={(e) => setFilter((f) => ({ ...f, status: (e.target.value || undefined) as UserFilter["status"] }))}
          >
            <option value="">Any status</option>
            {STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </Field>
        <Button type="submit" variant="outline" loading={users.isFetching && !users.isPending}>
          <Search />
          Search
        </Button>
      </form>
      <QueryBoundary q={users} what="the people">
        {(rows) =>
          rows.length === 0 ? (
            <div className="empty-state">No one matches. Try a different search.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Phone</th>
                    <th>Details</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((u) => (
                    <tr key={u.uid}>
                      <td className="font-medium">
                        {u.display_name || "Unnamed"}
                        <span className="table-sub">{u.email ?? u.uid}</span>
                      </td>
                      <td>{u.role}</td>
                      <td>
                        <span className="status-badge">
                          <span />
                          {u.status}
                        </span>
                      </td>
                      <td>{u.phone ?? "None"}</td>
                      <td>{detailsOf(u.details)}</td>
                      <td>
                        <Button size="sm" variant="ghost" aria-label={`Edit ${u.display_name || u.uid}`} onClick={() => setEditing(u.uid)}>
                          <Pencil />
                          Edit
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </QueryBoundary>
      {editing && <EditPerson uid={editing} onClose={() => setEditing(null)} />}
    </section>
  );
}

function detailsOf(d: Record<string, unknown> | undefined): string {
  if (!d) return "";
  const parts: string[] = [];
  if (typeof d.name === "string") parts.push(d.name);
  if (typeof d.tier === "number") parts.push(`tier ${d.tier}`);
  if (typeof d.max_tonnes === "number") parts.push(`${d.max_tonnes} t`);
  return parts.join(", ");
}

function EditPerson({ uid, onClose }: { uid: string; onClose: () => void }) {
  const profile = useUserProfile(uid);
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Edit details</DialogTitle>
        <DialogDescription>
          Changes apply at once. Jobs already assigned keep the terms they were quoted.
        </DialogDescription>
        <QueryBoundary q={profile} what="this person">
          {(p) => <ProfileForm key={JSON.stringify(p)} profile={p} admin onCancel={onClose} onSaved={onClose} />}
        </QueryBoundary>
      </DialogContent>
    </Dialog>
  );
}
