// The pure engine: a reducer over the domain model that implements every user
// story's happy and side path. No React, no I/O, no clock — `nowMs` is always
// a parameter so the offer ladder can be fast-forwarded deterministically in
// the demo and tested exactly.
//
// Each action is guarded by the state machine (stateMachine.ts) and by the
// domain invariants (ledger.ts, revenueShare.ts). An illegal action returns the
// state unchanged rather than throwing, so a mis-click in the demo UI degrades
// to a no-op instead of crashing the judge-facing screen.
import { rankFactories, factoryDistanceKm } from "./assignment";
import { nextTransporter, rankTransporters } from "./dispatch";
import { canTransition } from "./stateMachine";
import { DEFAULT_SHARES, split, type Shares } from "./revenueShare";
import type {
  Escalation,
  Farmer,
  Factory,
  Grade,
  Job,
  LedgerEntry,
  Lot,
  Offer,
  Order,
  Product,
  ResidueType,
  Transporter,
} from "./types";

/** Offer window before an unclaimed offer lapses and the ladder advances. */
export const OFFER_TTL_MS = 15 * 60 * 1000;
/** Platform's cut of every settled job, in basis points (15%). */
export const PLATFORM_FEE_BPS = 1500;
/** Haulage the farmer is paid on top of the factory price, per tonne (paisa). */
export const TRANSPORT_RATE_PER_TONNE = 80_000;

export interface DomainState {
  farmers: Farmer[];
  transporters: Transporter[];
  factories: Factory[];
  lots: Lot[];
  jobs: Job[];
  offers: Offer[];
  ledger: LedgerEntry[];
  products: Product[];
  orders: Order[];
  escalations: Escalation[];
  activity: string[];
}

export type DomainAction =
  | { type: "submitLot"; farmerId: string; residueType: ResidueType; quantityTonnes: number; village: string; district: string; pickupWindow: string; nowMs: number }
  | { type: "assignFactory"; jobId: string; factoryId: string; override: boolean }
  | { type: "fundEscrow"; jobId: string }
  | { type: "makeOffers"; jobId: string; nowMs: number }
  | { type: "tick"; nowMs: number }
  | { type: "acceptOffer"; offerId: string }
  | { type: "pickup"; jobId: string; photoRef: string; weightTonnes: number }
  | { type: "deliver"; jobId: string; photoRef: string; weightTonnes: number }
  | { type: "confirmWeight"; jobId: string; grade: Grade }
  | { type: "rejectLot"; jobId: string; reason: string }
  | { type: "verify"; jobId: string }
  | { type: "dispute"; jobId: string; note: string }
  | { type: "settle"; jobId: string; farmerShare: Shares }
  | { type: "addProduct"; factoryId: string; name: string; category: string; priceCents: number; unit: string; description: string; image: string }
  | { type: "toggleProduct"; productId: string }
  | { type: "createOrder"; productId: string; quantity: number; nowMs: number }
  | { type: "escalate"; callId: string; summary: string; transcript: string; nowMs: number }
  | { type: "approveTransporter"; transporterId: string }
  | { type: "reset"; next: DomainState };

let seq = 0;
const nextId = (prefix: string) => `${prefix}-${++seq}`;

/**
 * Escrow for a job: the factory's per-tonne price plus the haulage rate,
 * times tonnes, in paisa. This is the amount the factory must fund before
 * dispatch (FA1) and the pot the settlement splits (A3/FA3). Exported so the
 * quote a farmer hears (F2) and the ledger agree to the paisa.
 */
export const escrowFor = (job: Job, lot: Lot, factory: Factory): number =>
  Math.round(lot.quantityTonnes * (factory.pricePerTonneCents + TRANSPORT_RATE_PER_TONNE));

export function reducer(state: DomainState, action: DomainAction): DomainState {
  switch (action.type) {
    case "submitLot": return submitLot(state, action);
    case "assignFactory": return assignFactory(state, action);
    case "fundEscrow": return fundEscrow(state, action);
    case "makeOffers": return makeOffers(state, action);
    case "tick": return tick(state, action);
    case "acceptOffer": return acceptOffer(state, action);
    case "pickup": return pickup(state, action);
    case "deliver": return deliver(state, action);
    case "confirmWeight": return confirmWeight(state, action);
    case "rejectLot": return rejectLot(state, action);
    case "verify": return verify(state, action);
    case "dispute": return dispute(state, action);
    case "settle": return settle(state, action);
    case "addProduct": return addProduct(state, action);
    case "toggleProduct": return toggleProduct(state, action);
    case "createOrder": return createOrder(state, action);
    case "escalate": return escalate(state, action);
    case "approveTransporter": return approveTransporter(state, action);
    case "reset": return action.next;
  }
}

function log(state: DomainState, entry: string): string[] {
  return [entry, ...state.activity].slice(0, 12);
}

function jobById(state: DomainState, id: string): Job | undefined {
  return state.jobs.find((j) => j.id === id);
}

function mapJob(state: DomainState, id: string, fn: (j: Job) => Job): DomainState {
  return { ...state, jobs: state.jobs.map((j) => (j.id === id ? fn(j) : j)) };
}

function addLedger(state: DomainState, entry: Omit<LedgerEntry, "id">): LedgerEntry[] {
  return [...state.ledger, { ...entry, id: nextId("led") }];
}

// --- F1: the farmer reports a lot; A1 ranks factories and picks the best. ---
function submitLot(state: DomainState, a: Extract<DomainAction, { type: "submitLot" }>): DomainState {
  const farmer = state.farmers.find((f) => f.id === a.farmerId);
  if (!farmer || a.quantityTonnes <= 0) return state;

  const lot: Lot = {
    id: nextId("lot"),
    farmerId: a.farmerId,
    residueType: a.residueType,
    quantityTonnes: a.quantityTonnes,
    pickupWindow: a.pickupWindow,
    village: a.village,
    district: a.district,
    createdAt: a.nowMs,
  };
  const ranked = rankFactories(state.factories, {
    residueType: a.residueType,
    lat: farmer.lat,
    lon: farmer.lon,
    quantityTonnes: a.quantityTonnes,
  });
  const job: Job = {
    id: nextId("job"),
    lotId: lot.id,
    factoryId: ranked[0]?.factory.id ?? "",
    transporterId: null,
    state: "created",
    offeredTransporterIds: [],
    finalWeightTonnes: null,
    grade: null,
    rejectReason: null,
    ranking: ranked.map((r) => r.factory.id),
    assignedAt: a.nowMs,
    assignedOverride: false,
  };
  return {
    ...state,
    lots: [...state.lots, lot],
    jobs: [job, ...state.jobs],
    activity: log(state, `${farmer.name} reported ${a.quantityTonnes} t of ${a.residueType} in ${a.district}; ${ranked.length} factories ranked.`),
  };
}

// --- A1: admin can override the auto-assigned factory; overrides are logged. ---
function assignFactory(state: DomainState, a: Extract<DomainAction, { type: "assignFactory" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job || job.state !== "created") return state;
  if (!state.factories.some((f) => f.id === a.factoryId)) return state;
  return {
    ...mapJob(state, a.jobId, (j) => ({ ...j, factoryId: a.factoryId, assignedOverride: a.override })),
    activity: log(state, a.override
      ? `Admin overrode factory for ${a.jobId} → ${a.factoryId} (logged).`
      : `Factory set for ${a.jobId} → ${a.factoryId}.`),
  };
}

// --- FA1: the factory funds escrow; money enters the ledger. ---
function fundEscrow(state: DomainState, a: Extract<DomainAction, { type: "fundEscrow" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job || !canTransition(job.state, "funded")) return state;
  const lot = state.lots.find((l) => l.id === job.lotId);
  const factory = state.factories.find((f) => f.id === job.factoryId);
  if (!lot || !factory) return state;

  const amount = escrowFor(job, lot, factory);
  const next = mapJob(state, a.jobId, (j) => ({ ...j, state: "funded" }));
  return {
    ...next,
    ledger: addLedger(next, { jobId: a.jobId, kind: "escrow_in", amountCents: amount }),
    activity: log(next, `${factory.name} funded escrow for ${a.jobId}: PKR ${(amount / 100).toLocaleString("en-PK")}.`),
  };
}

// --- A2: funded jobs are put out to the transporter ladder. ---
function makeOffers(state: DomainState, a: Extract<DomainAction, { type: "makeOffers" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job) return state;
  // Legal from `funded` (first dispatch) and from `offered` (the A2 ladder
  // re-dispatch after expiry requeues the job). Anything else is a no-op.
  if (job.state !== "funded" && job.state !== "offered") return state;
  const lot = state.lots.find((l) => l.id === job.lotId);
  const farmer = lot && state.farmers.find((f) => f.id === lot.farmerId);
  if (!lot || !farmer) return state;

  const ladder = rankTransporters(state.transporters, farmer.lat, farmer.lon);
  const target = nextTransporter(ladder, job.offeredTransporterIds);
  if (!target) return state; // ladder exhausted; handled by tick/escalate

  const offer: Offer = {
    id: nextId("off"),
    jobId: a.jobId,
    transporterId: target,
    expiresAt: a.nowMs + OFFER_TTL_MS,
    status: "pending",
  };
  const next = {
    ...mapJob(state, a.jobId, (j) => ({ ...j, state: "offered" as const, offeredTransporterIds: [...j.offeredTransporterIds, target] })),
    offers: [offer, ...state.offers],
  };
  return { ...next, activity: log(next, `Offer ${offer.id} sent for ${a.jobId} (ladder).`) };
}

// --- A2: expire lapsed offers; if the ladder is empty the job is requeued. ---
function tick(state: DomainState, a: Extract<DomainAction, { type: "tick" }>): DomainState {
  const expired = state.offers.filter((o) => o.status === "pending" && a.nowMs >= o.expiresAt);
  if (expired.length === 0) return state;

  const expiredIds = new Set(expired.map((o) => o.id));
  let next: DomainState = {
    ...state,
    offers: state.offers.map((o) => (expiredIds.has(o.id) ? { ...o, status: "expired" as const } : o)),
  };
  for (const offer of expired) {
    const job = jobById(next, offer.jobId);
    if (!job || job.state !== "offered") continue;
    const stillPending = next.offers.some(
      (o) => o.jobId === offer.jobId && o.status === "pending" && !expiredIds.has(o.id),
    );
    if (stillPending) continue;
    const lot = next.lots.find((l) => l.id === job.lotId);
    const farmer = lot && next.farmers.find((f) => f.id === lot.farmerId);
    const ladder = farmer ? rankTransporters(next.transporters, farmer.lat, farmer.lon) : [];
    const target = nextTransporter(ladder, job.offeredTransporterIds);
    if (target) {
      const fresh: Offer = { id: nextId("off"), jobId: job.id, transporterId: target, expiresAt: a.nowMs + OFFER_TTL_MS, status: "pending" };
      next = { ...next, offers: [fresh, ...next.offers] };
      next = { ...mapJob(next, job.id, (j) => ({ ...j, offeredTransporterIds: [...j.offeredTransporterIds, target] })), activity: log(next, `Offer expired; ladder advanced to ${target} for ${job.id}.`) };
    } else {
      // Ladder exhausted: requeue as un-offered and flag for admin (A2 side path).
      next = { ...mapJob(next, job.id, (j) => ({ ...j, state: "created" as const })), activity: log(next, `Offer expired; ladder exhausted for ${job.id} — requeued for admin.`) };
      const autoEscalation: Escalation = { id: nextId("esc"), callId: job.id, summary: `Transporter ladder exhausted for ${job.id}`, transcript: "Auto-generated by offer expiry tick.", status: "open", createdAt: a.nowMs };
      next = { ...next, escalations: [autoEscalation, ...next.escalations] };
    }
  }
  return next;
}

// --- T1: one transporter wins; every other pending offer is withdrawn. ---
function acceptOffer(state: DomainState, a: Extract<DomainAction, { type: "acceptOffer" }>): DomainState {
  const offer = state.offers.find((o) => o.id === a.offerId);
  if (!offer || offer.status !== "pending") return state;
  const job = jobById(state, offer.jobId);
  if (!job || job.state !== "offered") return state;

  const next = {
    ...mapJob(state, offer.jobId, (j) => ({ ...j, state: "accepted" as const, transporterId: offer.transporterId })),
    offers: state.offers.map((o) =>
      o.jobId !== offer.jobId ? o : o.id === offer.id ? { ...o, status: "accepted" as const } : o.status === "pending" ? { ...o, status: "withdrawn" as const } : o,
    ),
  };
  const transporter = state.transporters.find((t) => t.id === offer.transporterId);
  return { ...next, activity: log(next, `${transporter?.name ?? offer.transporterId} accepted ${offer.jobId}; rival offers withdrawn.`) };
}

// --- T2: photo + weight at pickup and at delivery. ---
function pickup(state: DomainState, a: Extract<DomainAction, { type: "pickup" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job || !canTransition(job.state, "picked_up") || a.weightTonnes <= 0) return state;
  const next = mapJob(state, a.jobId, (j) => ({ ...j, state: "picked_up" as const }));
  return { ...next, activity: log(next, `${a.jobId} picked up (${a.weightTonnes} t, photo ${a.photoRef}).`) };
}

function deliver(state: DomainState, a: Extract<DomainAction, { type: "deliver" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job || !canTransition(job.state, "delivered") || a.weightTonnes <= 0) return state;
  const next = mapJob(state, a.jobId, (j) => ({ ...j, state: "delivered" as const, finalWeightTonnes: a.weightTonnes }));
  return { ...next, activity: log(next, `${a.jobId} delivered (${a.weightTonnes} t, photo ${a.photoRef}).`) };
}

// --- FA2: factory confirms the weighbridge grade, or rejects the lot. ---
function confirmWeight(state: DomainState, a: Extract<DomainAction, { type: "confirmWeight" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job || !canTransition(job.state, "confirmed")) return state;
  const next = mapJob(state, a.jobId, (j) => ({ ...j, state: "confirmed" as const, grade: a.grade }));
  return { ...next, activity: log(next, `${a.jobId} confirmed at ${a.grade.moistureBand} moisture (${(a.grade.confidence * 100).toFixed(0)}% confidence).`) };
}

function rejectLot(state: DomainState, a: Extract<DomainAction, { type: "rejectLot" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job || !canTransition(job.state, "rejected")) return state;
  const next = mapJob(state, a.jobId, (j) => ({ ...j, state: "rejected" as const, rejectReason: a.reason }));
  return { ...next, activity: log(next, `${a.jobId} rejected at weigh-in: ${a.reason}.`) };
}

// --- F4: the farmer confirms, which releases the payout, or disputes. ---
function verify(state: DomainState, a: Extract<DomainAction, { type: "verify" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job || !canTransition(job.state, "verified")) return state;
  const next = mapJob(state, a.jobId, (j) => ({ ...j, state: "verified" as const }));
  return { ...next, activity: log(next, `${a.jobId} verified by farmer; payout released.`) };
}

function dispute(state: DomainState, a: Extract<DomainAction, { type: "dispute" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job || !canTransition(job.state, "disputed")) return state;
  const disputeEscalation: Escalation = { id: nextId("esc"), callId: a.jobId, summary: `Farmer disputed ${a.jobId}`, transcript: a.note, status: "open", createdAt: Date.now() };
  const next = {
    ...mapJob(state, a.jobId, (j) => ({ ...j, state: "disputed" as const })),
    escalations: [disputeEscalation, ...state.escalations],
  };
  return { ...next, activity: log(next, `${a.jobId} disputed by farmer; frozen for admin.`) };
}

// --- A3 + FA3: settlement splits revenue and writes the ledger entries. ---
function settle(state: DomainState, a: Extract<DomainAction, { type: "settle" }>): DomainState {
  const job = jobById(state, a.jobId);
  if (!job || !canTransition(job.state, "settled")) return state;
  const lot = state.lots.find((l) => l.id === job.lotId);
  const factory = state.factories.find((f) => f.id === job.factoryId);
  if (!lot || !factory) return state;

  const total = escrowFor(job, lot, factory);
  const platformFee = Math.round((total * PLATFORM_FEE_BPS) / 10000);
  const farmerParts = split(total - platformFee, a.farmerShare);
  const farmerCents = farmerParts.farmer ?? 0;

  const entries: Omit<LedgerEntry, "id">[] = [
    { jobId: a.jobId, kind: "release_farmer", amountCents: farmerCents },
    { jobId: a.jobId, kind: "release_transporter", amountCents: Math.round(lot.quantityTonnes * TRANSPORT_RATE_PER_TONNE) },
    { jobId: a.jobId, kind: "platform_fee", amountCents: platformFee },
  ];
  const remainder = total - farmerCents - entries[1].amountCents - platformFee;
  if (remainder !== 0) entries.push({ jobId: a.jobId, kind: "refund", amountCents: remainder });

  let next = mapJob(state, a.jobId, (j) => ({ ...j, state: "settled" as const }));
  next = { ...next, ledger: [...next.ledger, ...entries.map((e) => ({ ...e, id: nextId("led") }))] };
  return { ...next, activity: log(next, `${a.jobId} settled: farmer PKR ${(farmerCents / 100).toLocaleString("en-PK")}, platform fee PKR ${(platformFee / 100).toLocaleString("en-PK")}.`) };
}

// --- FA3: factory lists a product; B1: buyer orders and revenue splits four ways. ---
function addProduct(state: DomainState, a: Extract<DomainAction, { type: "addProduct" }>): DomainState {
  const product: Product = {
    id: nextId("prd"),
    factoryId: a.factoryId,
    name: a.name,
    category: a.category,
    priceCents: a.priceCents,
    unit: a.unit,
    description: a.description,
    image: a.image,
    stock: 100,
    listed: true,
  };
  return { ...state, products: [product, ...state.products], activity: log(state, `${a.name} listed by ${a.factoryId}.`) };
}

function toggleProduct(state: DomainState, a: Extract<DomainAction, { type: "toggleProduct" }>): DomainState {
  return { ...state, products: state.products.map((p) => (p.id === a.productId ? { ...p, listed: !p.listed } : p)) };
}

function createOrder(state: DomainState, a: Extract<DomainAction, { type: "createOrder" }>): DomainState {
  const product = state.products.find((p) => p.id === a.productId);
  if (!product || a.quantity <= 0 || product.stock < a.quantity) return state;

  const total = product.priceCents * a.quantity;
  const order: Order = { id: nextId("ord"), productId: a.productId, quantity: a.quantity, totalCents: total, splitCents: split(total, DEFAULT_SHARES), createdAt: a.nowMs };
  const next: DomainState = {
    ...state,
    orders: [order, ...state.orders],
    products: state.products.map((p) => (p.id === a.productId ? { ...p, stock: p.stock - a.quantity } : p)),
  };
  return { ...next, activity: log(next, `Order ${order.id}: ${a.quantity} × ${product.name} — four-way split recorded.`) };
}

// --- F3: a call the agent could not handle is escalated for the admin queue. ---
function escalate(state: DomainState, a: Extract<DomainAction, { type: "escalate" }>): DomainState {
  const escalation: Escalation = { id: nextId("esc"), callId: a.callId, summary: a.summary, transcript: a.transcript, status: "open", createdAt: a.nowMs };
  return { ...state, escalations: [escalation, ...state.escalations], activity: log(state, `Escalated: ${a.summary}.`) };
}

// --- A2: admin approves a transporter, unlocking them for the ladder. ---
function approveTransporter(state: DomainState, a: Extract<DomainAction, { type: "approveTransporter" }>): DomainState {
  const transporter = state.transporters.find((t) => t.id === a.transporterId);
  if (!transporter || transporter.approved) return state;
  const next = { ...state, transporters: state.transporters.map((t) => (t.id === a.transporterId ? { ...t, approved: true } : t)) };
  return { ...next, activity: log(next, `Transporter ${transporter.name} approved.`) };
}
