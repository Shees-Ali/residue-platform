// Domain model for the residue marketplace, mirroring the API contracts
// (api/app/models/*) and the plan's job lifecycle (memory/implementation-plan.md).
// Money is integer minor units (paisa); shares are basis points summing to 10000.
// Field names are camelCase (TS convention); semantics match the API's snake_case.

export type ResidueType = "rice_straw" | "wheat_straw" | "cotton_stalk" | "sugarcane_trash";

export type JobState =
  | "created"
  | "funded"
  | "offered"
  | "accepted"
  | "picked_up"
  | "delivered"
  | "confirmed"
  | "verified"
  | "settled"
  | "rejected"
  | "disputed";

export type OfferStatus = "pending" | "accepted" | "expired" | "withdrawn";

export type LedgerKind =
  | "escrow_in"
  | "release_farmer"
  | "release_transporter"
  | "platform_fee"
  | "refund";

export interface Farmer {
  id: string;
  name: string;
  phone: string;
  district: string;
  village: string;
  lat: number;
  lon: number;
}

export interface Transporter {
  id: string;
  name: string;
  phone: string;
  tier: 1 | 2 | 3;
  approved: boolean;
  lat: number;
  lon: number;
}

export interface Factory {
  id: string;
  name: string;
  acceptedResidues: ResidueType[];
  lat: number;
  lon: number;
  pricePerTonneCents: number;
}

export interface Lot {
  id: string;
  farmerId: string;
  residueType: ResidueType;
  quantityTonnes: number;
  pickupWindow: string;
  village: string;
  district: string;
  createdAt: number; // epoch ms
}

/** What factory scoring actually needs from a lot (mirrors api LotRequest). */
export interface LotRequest {
  residueType: ResidueType;
  lat: number;
  lon: number;
  quantityTonnes: number;
}

export interface Grade {
  residueType: ResidueType;
  moistureBand: "low" | "medium" | "high";
  contaminationFlags: string[];
  confidence: number;
  disclaimer: string; // visual estimate only; weighbridge confirmation required
}

export interface Job {
  id: string;
  lotId: string;
  factoryId: string;
  transporterId: string | null;
  state: JobState;
  offeredTransporterIds: string[]; // the offer ladder (ranked, tried)
  finalWeightTonnes: number | null;
  grade: Grade | null;
  rejectReason: string | null;
  ranking: string[]; // factory ids, best first (A1)
  assignedAt: number; // epoch ms
  assignedOverride: boolean; // admin overrode the auto-pick (A1, logged)
}

export interface Offer {
  id: string;
  jobId: string;
  transporterId: string;
  expiresAt: number; // epoch ms
  status: OfferStatus;
}

export interface LedgerEntry {
  id: string;
  jobId: string;
  kind: LedgerKind;
  amountCents: number; // always >= 0
}

export interface Product {
  id: string;
  factoryId: string;
  name: string;
  category: string;
  priceCents: number; // per unit, paisa
  unit: string;
  description: string;
  image: string;
  stock: number;
  listed: boolean;
}

export interface Order {
  id: string;
  productId: string;
  quantity: number;
  totalCents: number;
  splitCents: Record<string, number>; // farmer/factory/ngo/platform, sums to totalCents
  createdAt: number;
}

export interface Escalation {
  id: string;
  callId: string;
  summary: string;
  transcript: string;
  status: "open" | "resolved";
  createdAt: number;
}

export interface RankedFactory {
  factory: Factory;
  score: number;
  distanceKm: number;
}
