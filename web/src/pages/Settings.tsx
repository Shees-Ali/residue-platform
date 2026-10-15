import { PageHeading } from "@/components/fasalloop/common";
import { useProfile } from "@/api/hooks";
import { useAuth } from "@/auth/AuthProvider";
import { ProfileForm } from "@/components/live/ProfileForm";
import { QueryBoundary } from "@/components/live/common";

/** Everyone's own details. A factory edits its name, price, residues and place; a transporter its
 * phone and base. Changes apply at once and only affect later lots and offers. */
export default function Settings() {
  const profile = useProfile();
  const { refresh } = useAuth();
  return (
    <>
      <PageHeading
        eyebrow="MY DETAILS"
        title="Keep your details up to date."
        description="Changes apply at once. Jobs already assigned keep the terms they were quoted."
      />
      <div className="auth-card wide">
        <QueryBoundary q={profile} what="your details">
          {(p) => <ProfileForm key={JSON.stringify(p)} profile={p} onSaved={() => void refresh()} />}
        </QueryBoundary>
      </div>
    </>
  );
}
