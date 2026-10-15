import { useState } from "react";
import { Leaf } from "lucide-react";
import { useProfile } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { ProfileForm } from "@/components/live/ProfileForm";
import { QueryBoundary } from "@/components/live/common";
import { useAuth } from "@/auth/AuthProvider";
import { RedirectIfSettled } from "@/auth/guards";

export default function Pending() {
  const { state, refresh, signOut } = useAuth();
  const [checking, setChecking] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const suspended = state.status === "suspended";
  const user = state.status === "pending" || state.status === "suspended" ? state.user : null;
  return (
    <div className="auth-page">
      <RedirectIfSettled stay={["pending", "suspended"]} />
      <div className="auth-card text-center">
        <div className="auth-brand" style={{ justifyContent: "center" }}>
          <Leaf size={22} /> Residue Platform
        </div>
        <h1>{suspended ? "This account is suspended" : "Waiting for approval"}</h1>
        <p className="lead">
          {suspended
            ? "An admin has blocked this account. Contact the platform team if you think this is a mistake."
            : `Thanks${user?.display_name ? `, ${user.display_name}` : ""}. An admin reviews every ${
                user?.role ?? "new"
              } account before it can start. You can close this page and come back later.`}
        </p>
        <div className="auth-stack">
          {!suspended && (
            <Button
              type="button"
              loading={checking}
              disabled={leaving}
              onClick={async () => {
                setChecking(true);
                try {
                  await refresh();
                } finally {
                  setChecking(false);
                }
              }}
            >
              Check again
            </Button>
          )}
          {!suspended && (
            <Button type="button" variant="outline" disabled={leaving} onClick={() => setEditing(true)}>
              Edit my details
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            loading={leaving}
            disabled={checking}
            onClick={async () => {
              setLeaving(true);
              try {
                await signOut();
              } finally {
                setLeaving(false);
              }
            }}
          >
            Sign out
          </Button>
        </div>
      </div>
      {editing && <EditDetails onClose={() => setEditing(false)} />}
    </div>
  );
}

/** A pending account can fix a typo in what it signed up with while it waits. */
function EditDetails({ onClose }: { onClose: () => void }) {
  const profile = useProfile();
  const { refresh } = useAuth();
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="form-dialog">
        <DialogTitle>Edit my details</DialogTitle>
        <DialogDescription>You can change these while you wait for approval.</DialogDescription>
        <QueryBoundary q={profile} what="your details">
          {(p) => (
            <ProfileForm
              key={JSON.stringify(p)}
              profile={p}
              onCancel={onClose}
              onSaved={() => void refresh().then(onClose)}
            />
          )}
        </QueryBoundary>
      </DialogContent>
    </Dialog>
  );
}
