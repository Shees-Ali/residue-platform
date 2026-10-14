// Seed world for the demo engine, mirroring seed/seed.py (synthetic only, paisa,
// 4 factories, 8 transporters). Prices are in the same 400k–900k paisa/tonne
// band seed.py generates, so the ledger numbers the judge sees are consistent
// with the reference data the API will load.
//
// Jobs are pre-loaded across the lifecycle so the demo lands mid-story rather
// than empty, and one transporter (t-unresponsive) never accepts, so the offer
// ladder and its expiry tick are visible on first load.
import { rankFactories } from "./assignment";
import { OFFER_TTL_MS, TRANSPORT_RATE_PER_TONNE, type DomainState } from "./engine";
import type { Job, LedgerEntry, Offer } from "./types";

const NOW = Date.UTC(2026, 9, 15, 12, 0, 0);

export function seedDomain(): DomainState {
  const farmers = [
    { id: "f1", name: "Muhammad Aslam", phone: "+923000000001", district: "Sheikhupura", village: "Muridke", lat: 31.77, lon: 73.05 },
    { id: "f2", name: "Ahmed Raza", phone: "+923000000002", district: "Gujranwala", village: "Kamoke", lat: 32.19, lon: 73.98 },
    { id: "f3", name: "Bilal Hussain", phone: "+923000000003", district: "Faisalabad", village: "Jaranwala", lat: 31.33, lon: 73.42 },
  ];

  const transporters = [
    { id: "t1", name: "Swift Haulage", phone: "+923000001001", tier: 1 as const, approved: true, lat: 31.78, lon: 73.06 },
    { id: "t2", name: "Delta Freight", phone: "+923000001002", tier: 2 as const, approved: true, lat: 31.9, lon: 73.2 },
    { id: "t3", name: "Ravi Logistics", phone: "+923000001003", tier: 1 as const, approved: true, lat: 31.55, lon: 74.34 },
    { id: "t4", name: "Chenab Carriers", phone: "+923000001004", tier: 3 as const, approved: true, lat: 31.6, lon: 73.2 },
    { id: "t5", name: "Satluj Transit", phone: "+923000001005", tier: 2 as const, approved: true, lat: 31.4, lon: 73.1 },
    { id: "t6", name: "Jhelum Movers", phone: "+923000001006", tier: 3 as const, approved: true, lat: 32.1, lon: 73.5 },
    // Never accepts — drives the ladder/expiry path for the A2 story.
    { id: "t-unresponsive", name: "Idle Truck Co", phone: "+923000001007", tier: 2 as const, approved: true, lat: 31.76, lon: 73.04 },
    // Unapproved: must not receive offers until A2 approves them.
    { id: "t8", name: "New Recruit", phone: "+923000001008", tier: 1 as const, approved: false, lat: 31.75, lon: 73.07 },
  ];

  const factories = [
    { id: "fac1", name: "GreenCycle Industries", acceptedResidues: ["rice_straw" as const, "wheat_straw" as const], lat: 31.52, lon: 74.36, pricePerTonneCents: 650_000 },
    { id: "fac2", name: "Punjab BioPower", acceptedResidues: ["rice_straw" as const, "wheat_straw" as const, "cotton_stalk" as const], lat: 31.71, lon: 73.01, pricePerTonneCents: 520_000 },
    { id: "fac3", name: "Faisalabad Agri-Recycle", acceptedResidues: ["cotton_stalk" as const, "sugarcane_trash" as const], lat: 31.45, lon: 73.13, pricePerTonneCents: 780_000 },
    { id: "fac4", name: "Okara Fiber Works", acceptedResidues: ["wheat_straw" as const, "sugarcane_trash" as const], lat: 30.62, lon: 73.35, pricePerTonneCents: 440_000 },
  ];

  const products = [
    { id: "prd1", factoryId: "fac1", name: "Biomass pellets", category: "Energy", priceCents: 2_400_00, unit: "per 40 kg bag", description: "Dense pellets pressed from rice straw.", image: "/src/assets/briquettes.jpg", stock: 300, listed: true },
    { id: "prd2", factoryId: "fac2", name: "Compressed briquettes", category: "Energy", priceCents: 1_900_00, unit: "per 20 kg bundle", description: "Briquettes from mixed residue.", image: "/src/assets/briquettes.jpg", stock: 180, listed: true },
    { id: "prd3", factoryId: "fac3", name: "Compost", category: "Farming & Garden", priceCents: 900_00, unit: "per 25 kg bag", description: "Nutrient-rich compost from cotton stalk.", image: "/src/assets/compost.jpg", stock: 420, listed: true },
  ];

  // A settled job so the ledger invariant is visibly true and the impact
  // counter is non-zero on first load.
  const settledLot = { id: "lot-settled", farmerId: "f1", residueType: "rice_straw" as const, quantityTonnes: 2, pickupWindow: "2026-10-10", village: "Muridke", district: "Sheikhupura", createdAt: NOW - 86_400_000 * 5 };
  const settledJob: Job = { id: "job-settled", lotId: settledLot.id, factoryId: "fac1", transporterId: "t1", state: "settled", offeredTransporterIds: ["t1"], finalWeightTonnes: 1.95, grade: null, rejectReason: null, ranking: ["fac1"], assignedAt: NOW - 86_400_000 * 5, assignedOverride: false };
  const settledLedger = settledLedgerFor(settledJob, settledLot.quantityTonnes);

  // A job sitting at `offered` with an unresponsive transporter, so the ladder
  // and expiry are visible immediately (A2).
  const offeredLot = { id: "lot-offered", farmerId: "f2", residueType: "wheat_straw" as const, quantityTonnes: 3.5, pickupWindow: "2026-10-16", village: "Kamoke", district: "Gujranwala", createdAt: NOW - 3_600_000 };
  const offeredJob: Job = { id: "job-offered", lotId: offeredLot.id, factoryId: "fac1", transporterId: null, state: "offered", offeredTransporterIds: ["t-unresponsive"], finalWeightTonnes: null, grade: null, rejectReason: null, ranking: ["fac1", "fac2"], assignedAt: NOW - 3_600_000, assignedOverride: false };
  const pendingOffer: Offer = { id: "off-pending", jobId: offeredJob.id, transporterId: "t-unresponsive", expiresAt: NOW + 4 * 60_000, status: "pending" };

  // A job awaiting FA1 funding (created, factory auto-picked).
  const createdLot = { id: "lot-created", farmerId: "f3", residueType: "cotton_stalk" as const, quantityTonnes: 4, pickupWindow: "2026-10-17", village: "Jaranwala", district: "Faisalabad", createdAt: NOW - 600_000 };
  const createdJob: Job = { id: "job-created", lotId: createdLot.id, factoryId: "fac3", transporterId: null, state: "created", offeredTransporterIds: [], finalWeightTonnes: null, grade: null, rejectReason: null, ranking: ["fac3"], assignedAt: NOW - 600_000, assignedOverride: false };

  // A job sitting at `delivered`, waiting on the FA2 weighbridge: the factory
  // confirms the weight and grade (or rejects with a reason).
  const deliveredLot = { id: "lot-delivered", farmerId: "f1", residueType: "rice_straw" as const, quantityTonnes: 2.5, pickupWindow: "2026-10-12", village: "Muridke", district: "Sheikhupura", createdAt: NOW - 86_400_000 * 2 };
  const deliveredJob: Job = { id: "job-delivered", lotId: deliveredLot.id, factoryId: "fac1", transporterId: "t2", state: "delivered", offeredTransporterIds: ["t2"], finalWeightTonnes: 2.42, grade: null, rejectReason: null, ranking: ["fac1"], assignedAt: NOW - 86_400_000 * 2, assignedOverride: false };

  // A job at `confirmed`, waiting on the F4 farmer verification.
  const confirmedLot = { id: "lot-confirmed", farmerId: "f2", residueType: "wheat_straw" as const, quantityTonnes: 1.8, pickupWindow: "2026-10-11", village: "Kamoke", district: "Gujranwala", createdAt: NOW - 86_400_000 * 3 };
  const confirmedJob: Job = { id: "job-confirmed", lotId: confirmedLot.id, factoryId: "fac2", transporterId: "t3", state: "confirmed", offeredTransporterIds: ["t3"], finalWeightTonnes: 1.75, grade: null, rejectReason: null, ranking: ["fac2"], assignedAt: NOW - 86_400_000 * 3, assignedOverride: false };

  return {
    farmers,
    transporters,
    factories,
    lots: [settledLot, offeredLot, createdLot, deliveredLot, confirmedLot],
    jobs: [createdJob, offeredJob, settledJob, deliveredJob, confirmedJob],
    offers: [pendingOffer],
    ledger: settledLedger,
    products,
    orders: [],
    escalations: [],
    activity: [
      "GreenCycle Industries funded escrow for job-settled: PKR 1,462,000.",
      "Swift Haulage accepted job-settled; rival offers withdrawn.",
      "Muhammad Aslam reported 2 t of rice_straw in Sheikhupura; 2 factories ranked.",
    ],
  };
}

// The full settlement ledger for the pre-settled job, so escrowBalanced(ledger)
// is true on load and the A3 impact counter has something to show.
function settledLedgerFor(job: Job, quantityTonnes: number): LedgerEntry[] {
  const price = 650_000; // fac1
  const total = Math.round(quantityTonnes * (price + TRANSPORT_RATE_PER_TONNE));
  const platformFee = Math.round((total * 1500) / 10000);
  const farmerShare = Math.round(((total - platformFee) * 5000) / 10000);
  const transporter = Math.round(quantityTonnes * TRANSPORT_RATE_PER_TONNE);
  const remainder = total - farmerShare - transporter - platformFee;
  const entries: LedgerEntry[] = [
    { id: "led-1", jobId: job.id, kind: "escrow_in", amountCents: total },
    { id: "led-2", jobId: job.id, kind: "release_farmer", amountCents: farmerShare },
    { id: "led-3", jobId: job.id, kind: "release_transporter", amountCents: transporter },
    { id: "led-4", jobId: job.id, kind: "platform_fee", amountCents: platformFee },
  ];
  if (remainder !== 0) entries.push({ id: "led-5", jobId: job.id, kind: "refund", amountCents: remainder });
  return entries;
}

// Re-exported for callers that want to rank factories against a seed farmer.
export { rankFactories, OFFER_TTL_MS };
