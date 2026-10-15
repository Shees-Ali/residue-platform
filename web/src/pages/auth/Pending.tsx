import { useState } from "react";
import { Leaf } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/auth/AuthProvider";
import { RedirectIfSettled } from "@/auth/guards";

export default function Pending() {
  const { state, refresh, signOut } = useAuth();
  const [checking, setChecking] = useState(false);
  const [leaving, setLeaving] = useState(false);
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
    </div>
  );
}
