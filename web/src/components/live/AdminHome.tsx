import { Factory as FactoryIcon, Leaf, ShoppingBag, Truck, Users, Wallet } from "lucide-react";
import { useStats } from "@/api/hooks";
import { PageHeading, Stat, pkr } from "@/components/fasalloop/common";
import { Skeleton } from "@/components/ui/spinner";
import { PendingApprovals } from "@/components/fasalloop/approvals";
import { AdminDispatch } from "./AdminDispatch";
import { AdminLedger, EscalationQueue, ImpactPanel } from "./AdminLedger";
import { AdminLotsSection } from "./AdminLotsSection";
import { LiveMap } from "./TrackViews";
import { AdminPeople } from "./AdminPeople";

function StatsStrip() {
  const stats = useStats();
  if (stats.isPending) {
    return (
      <div className="stats-grid admin-stats" aria-busy="true">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
    );
  }
  if (stats.isError) return null; // the error is toasted; the panels below still work
  const s = stats.data;
  return (
    <div className="stats-grid admin-stats">
      <Stat live label="Farmers" value={s.farmers} icon={Users} note="On the platform" />
      <Stat live label="Live jobs" value={s.live_jobs} icon={Truck} note="Not yet settled" tone="gold" />
      <Stat live label="Transporters" value={s.transporters} icon={Truck} note={`${s.transporters_waiting_approval} awaiting approval`} />
      <Stat live label="Factories" value={s.factories} icon={FactoryIcon} note="Processing partners" />
      <Stat live label="Residue kept from burning" value={`${s.tonnes_diverted.toFixed(1)} t`} icon={Leaf} note={`${s.jobs_settled} jobs settled`} tone="gold" />
      <Stat live label="Held in escrow" value={pkr(s.escrow_held)} icon={Wallet} note={`${s.open_escalations} need a person`} />
      <Stat live label="Marketplace orders" value={s.orders} icon={ShoppingBag} note="Four-way split recorded" />
    </div>
  );
}

/** The admin page, all on real data. */
export function AdminHome() {
  return (
    <>
      <PageHeading
        eyebrow="ADMIN OVERVIEW"
        title="A growing circular economy."
        description="One connected view of farms, jobs, factories, money and impact."
      />
      <PendingApprovals />
      <StatsStrip />
      <AdminPeople />
      <AdminLotsSection />
      <AdminDispatch />
      <LiveMap />
      <EscalationQueue />
      <AdminLedger />
      <ImpactPanel />
    </>
  );
}
