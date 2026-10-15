import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/api/client";
import { apiErrorFrom } from "@/api/query";
import { PageHeading } from "@/components/fasalloop/common";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/auth/AuthProvider";
import { PhoneVerifier } from "@/auth/PhoneVerifier";
import { ConfirmSection, Payments } from "./FarmerConfirm";
import { LotForm } from "./LotForm";
import { LiveLabel, MyRequests } from "./lots";

/** The farmer's page: report residue, and follow every request. Real data. */
export function FarmerHome() {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const isFarmer = user?.role === "farmer";
  const linked = user?.farmer_linked === true;
  const first = (user?.display_name ?? "").split(" ")[0] || "there";

  async function linkPhone() {
    const { data, error, response } = await api.POST("/api/me/link-phone");
    if (!data) {
      const err = apiErrorFrom(error, response.status);
      toast.error(err.message);
      return;
    }
    toast.info("Phone verified. You can report residue now.");
    await refresh();
  }

  return (
    <>
      <PageHeading
        eyebrow="FARMER PORTAL"
        title={`Assalam-o-Alaikum, ${first}!`}
        description="Report your crop residue and follow each request until you are paid."
        action={
          isFarmer && linked ? (
            <Button onClick={() => setOpen(true)} className="h-11">
              <Plus />
              Report residue
            </Button>
          ) : undefined
        }
      />

      {!isFarmer && (
        <p className="auth-note mb-4">
          You are signed in as {user?.role}. Farmers report and follow their residue here.
        </p>
      )}

      {isFarmer && !linked && (
        <section className="auth-card wide mb-6" aria-label="Verify your phone">
          <h1>Verify your phone to report residue</h1>
          <p className="lead">
            Your requests are tied to your phone number, so we need to confirm it is yours. Farmers who
            called us before see those requests here too.
          </p>
          <PhoneVerifier onVerified={linkPhone} />
        </section>
      )}

      {isFarmer && linked && <ConfirmSection />}

      {isFarmer && linked && (
        <>
          <div className="section-title">
            <h2>Your requests</h2>
            <LiveLabel />
          </div>
          <MyRequests />
          <Payments />
        </>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="form-dialog">
          <DialogTitle>Report residue</DialogTitle>
          <DialogDescription>
            The same details we take on a phone call. We match your residue to the best factory.
          </DialogDescription>
          <LotForm mode="farmer" onDone={() => setOpen(false)} onCancel={() => setOpen(false)} />
        </DialogContent>
      </Dialog>
    </>
  );
}
