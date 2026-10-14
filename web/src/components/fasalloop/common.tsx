import { ArrowUpRight, type LucideIcon, Check, Circle } from 'lucide-react';
import type { ReactNode } from 'react';
import { type Collection, type Status, formatDate } from './demo-state';
import type { Grade, JobState, LedgerEntry } from '@/lib/domain/types';

/* ------------------------------------------------------------------ *
 * Shared page chrome (Phase 0) — unchanged.
 * ------------------------------------------------------------------ */

export function PageHeading({eyebrow,title,description,action}:{eyebrow:string;title:string;description:string;action?:ReactNode}){return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p className="text-muted-foreground mt-2">{description}</p></div>{action}</div>;}
export function Stat({label,value,icon:Icon,note,tone='green'}:{label:string;value:string|number;icon:LucideIcon;note:string;tone?:string}){return <div className="stat-card"><div className="flex justify-between items-center"><span className="text-sm text-muted-foreground">{label}</span><span className={`stat-icon ${tone}`}><Icon size={19}/></span></div><div className="stat-value">{value}</div><div className="text-xs text-muted-foreground flex items-center gap-1.5"><ArrowUpRight size={13} className="text-primary"/>Demo · {note}</div></div>;}
export function StatusBadge({status}:{status:Status}){return <span className={`status-badge status-${status.toLowerCase().replace(' ','-')}`}><span/>{status}</span>;}
export function DemoLabel(){return <span className="demo-label"><span/>Demo data</span>;}
export function SectionTitle({title,children}:{title:string;children?:ReactNode}){return <div className="section-title"><h2>{title}</h2><div className="flex items-center gap-3"><DemoLabel/>{children}</div></div>;}
export function RequestTable({requests,admin=false}:{requests:Collection[];admin?:boolean}){return <div className="table-wrap"><table><thead><tr><th>Request ID</th>{admin&&<th>Farmer</th>}<th>Crop residue</th><th>Quantity</th><th>Location</th><th>Pickup date</th><th>Status</th></tr></thead><tbody>{requests.map(r=><tr key={r.id}><td className="font-medium text-primary">{r.id}</td>{admin&&<td>{r.name}</td>}<td>{r.crop}</td><td>{r.quantity} tonnes</td><td>{r.district}<span className="table-sub">{r.village}</span></td><td>{formatDate(r.date)}</td><td><StatusBadge status={r.status}/></td></tr>)}</tbody></table>{!requests.length&&<p className="p-8 text-center text-muted-foreground">No collection requests yet.</p>}</div>;}
export function Tracker({status}:{status:Status}){const stages=['Submitted','Factory accepted','Pickup started','Delivered','Received'];const idx=({Pending:0,Accepted:1,'In transit':2,Delivered:3,Received:4,Rejected:0})[status];return <div className="tracker">{stages.map((s,i)=><div className={`tracker-step ${i<=idx?'done':''}`} key={s}><span>{i<=idx?<Check size={13}/>:<Circle size={11}/>}</span><small>{s}</small></div>)}</div>;}

/* ------------------------------------------------------------------ *
 * Phase 2 — domain widgets. These read the new lifecycle model.
 * ------------------------------------------------------------------ */

/** Human labels for the 9 main states + 2 side states. */
export const JOB_STATE_LABEL: Record<JobState, string> = {
  created: 'Created',
  funded: 'Escrow funded',
  offered: 'Offered',
  accepted: 'Accepted',
  picked_up: 'Picked up',
  delivered: 'Delivered',
  confirmed: 'Weight confirmed',
  verified: 'Verified',
  settled: 'Settled',
  rejected: 'Rejected',
  disputed: 'Disputed',
};

// The happy-path spine. Side states (rejected/disputed) fall outside it and are
// rendered as a terminal banner instead of a step highlight.
const JOB_STAGES: { state: JobState; label: string }[] = [
  { state: 'created', label: 'Created' },
  { state: 'funded', label: 'Funded' },
  { state: 'offered', label: 'Offered' },
  { state: 'accepted', label: 'Accepted' },
  { state: 'picked_up', label: 'Picked up' },
  { state: 'delivered', label: 'Delivered' },
  { state: 'confirmed', label: 'Confirmed' },
  { state: 'verified', label: 'Verified' },
  { state: 'settled', label: 'Settled' },
];

const SIDE_STATES: JobState[] = ['rejected', 'disputed'];

/**
 * Lifecycle tracker for the 9-state job machine. Highlights every stage up to
 * and including the current one; a side state renders as a terminal banner so
 * a rejected or disputed job never looks like it is still moving.
 */
export function JobTracker({ state }: { state: JobState }) {
  if (SIDE_STATES.includes(state)) {
    return (
      <div className="tracker" role="status">
        <div className="invariant invariant-hold">
          <span>{state === 'rejected' ? 'Lot rejected at weigh-in' : 'Disputed — payout frozen'}</span>
        </div>
      </div>
    );
  }
  const idx = JOB_STAGES.findIndex((s) => s.state === state);
  return (
    <div className="tracker">
      {JOB_STAGES.map((s, i) => (
        <div className={`tracker-step ${i <= idx ? 'done' : ''}`} key={s.state}>
          <span>{i <= idx ? <Check size={13} /> : <Circle size={11} />}</span>
          <small>{s.label}</small>
        </div>
      ))}
    </div>
  );
}

/** Money in paisa → "PKR 1,462,000". Never a float. */
export const pkr = (paisa: number): string =>
  `PKR ${Math.round(paisa).toLocaleString('en-PK')}`;

/** A single key/value row (dt/dd semantics via spans). */
export function KV({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="kv">
      <span className="kv-k">{k}</span>
      <span className="kv-v">{v}</span>
    </div>
  );
}

/** A neutral chip; `tone` picks the palette. */
export function Pill({ children, tone }: { children: ReactNode; tone?: 'gold' | 'live' }) {
  return <span className={`pill${tone ? ` pill-${tone}` : ''}`}>{children}</span>;
}

/**
 * AI grade card (FA2). Always labelled a visual estimate — the weighbridge is
 * the source of truth, and the disclaimer is not optional.
 */
export function GradeCard({ grade }: { grade: Grade }) {
  return (
    <div className="job-card" style={{ padding: 14 }}>
      <div className="flex items-center justify-between">
        <span className="eyebrow">AI GRADING</span>
        <Pill tone={grade.confidence >= 0.8 ? 'live' : 'gold'}>
          {(grade.confidence * 100).toFixed(0)}% confidence
        </Pill>
      </div>
      <dl style={{ margin: '10px 0 0' }}>
        <KV k="Residue" v={grade.residueType.replace('_', ' ')} />
        <KV k="Moisture band" v={grade.moistureBand} />
        <KV
          k="Contamination"
          v={grade.contaminationFlags.length ? grade.contaminationFlags.join(', ') : 'None flagged'}
        />
      </dl>
      <p className="text-xs text-muted-foreground mt-3">{grade.disclaimer}</p>
    </div>
  );
}

const LEDGER_LABEL: Record<LedgerEntry['kind'], string> = {
  escrow_in: 'Escrow in',
  release_farmer: '→ Farmer',
  release_transporter: '→ Transporter',
  platform_fee: 'Platform fee',
  refund: 'Refund',
};

/**
 * Ledger table + invariant badge (A3). `heldCents` is money still in escrow
 * for jobs that have not settled, which is why the ledger is legitimately
 * unbalanced while the pipeline is live.
 */
export function LedgerPanel({ entries, heldCents }: { entries: LedgerEntry[]; heldCents: number }) {
  const inflow = entries.filter((e) => e.kind === 'escrow_in').reduce((n, e) => n + e.amountCents, 0);
  const outflow = entries.filter((e) => e.kind !== 'escrow_in').reduce((n, e) => n + e.amountCents, 0);
  const balanced = inflow === outflow;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <span className={`invariant ${balanced ? 'invariant-ok' : 'invariant-hold'}`}>
          <span>{balanced ? '✓' : '⏸'}</span>
          {balanced ? 'Ledger balanced' : 'Escrow in flight'}
        </span>
        <Pill>In {pkr(inflow)}</Pill>
        <Pill>Out {pkr(outflow)}</Pill>
        <Pill tone="gold">Held {pkr(heldCents)}</Pill>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Entry</th><th>Job</th><th>Amount</th></tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id}>
                <td className="font-medium">{LEDGER_LABEL[e.kind]}</td>
                <td className="text-muted-foreground">{e.jobId}</td>
                <td>{pkr(e.amountCents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!entries.length && <p className="p-8 text-center text-muted-foreground">No ledger entries yet.</p>}
      </div>
    </div>
  );
}

const SPLIT_COLORS: Record<string, string> = {
  farmer: 'var(--primary)',
  factory: 'var(--gold, #d6a64d)',
  ngo: '#7aa88f',
  platform: 'var(--muted-foreground)',
};

/**
 * Four-way revenue split (FA3/B1). Renders one sale as stacked shares plus a
 * legend; the parts always sum to the total by construction.
 */
export function SplitBreakdown({ totalCents, splitCents }: { totalCents: number; splitCents: Record<string, number> }) {
  const order = ['farmer', 'factory', 'ngo', 'platform'];
  return (
    <div>
      <div className="split-bar">
        {order.map((k) =>
          totalCents > 0 ? (
            <span
              key={k}
              style={{ width: `${((splitCents[k] ?? 0) / totalCents) * 100}%`, background: SPLIT_COLORS[k] }}
            />
          ) : null,
        )}
      </div>
      <div className="split-legend">
        {order.map((k) => (
          <span key={k}>
            <span className="swatch" style={{ background: SPLIT_COLORS[k] }} />
            {k} · {pkr(splitCents[k] ?? 0)}
          </span>
        ))}
      </div>
    </div>
  );
}
