import { ArrowUpRight, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import type { JobState } from '@/lib/domain/types';

/* Shared page chrome and money helpers used by the live screens. */

export function PageHeading({eyebrow,title,description,action}:{eyebrow:string;title:string;description:string;action?:ReactNode}){return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p className="text-muted-foreground mt-2">{description}</p></div>{action}</div>;}
export function Stat({label,value,icon:Icon,note,tone='green',live=false}:{label:string;value:string|number;icon:LucideIcon;note:string;tone?:string;live?:boolean}){return <div className="stat-card"><div className="flex justify-between items-center"><span className="text-sm text-muted-foreground">{label}</span><span className={`stat-icon ${tone}`}><Icon size={19}/></span></div><div className="stat-value">{value}</div><div className="text-xs text-muted-foreground flex items-center gap-1.5"><ArrowUpRight size={13} className="text-primary"/>{live ? note : `Demo · ${note}`}</div></div>;}

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

/** Money in paisa → whole rupees, e.g. 146200000 → "PKR 1,462,000". The API sends paisa. */
export const pkr = (paisa: number): string =>
  `PKR ${Math.round(paisa / 100).toLocaleString('en-PK')}`;

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
