// The 9-state job lifecycle plus two side states, mirroring the plan
// (memory/implementation-plan.md) and the happy path
// F1→F2→A1→FA1→T1→T2→FA2→F4→A3→FA3→B1.
//
//   created → funded → offered → accepted → picked_up → delivered
//           → confirmed → verified → settled
//
// Side states: `rejected` (FA2 rejects the lot at weigh-in) and `disputed`
// (F4 farmer disputes the weight/quality). Both are terminal in this machine;
// a dispute is frozen for admin (A2) resolution rather than auto-resolved.
//
// Offer expiry (A2) is NOT a job state: an expiring offer re-dispatches the
// ladder (nextTransporter) and the job stays `offered`. Only once the ladder
// is exhausted does the job fall back, which the engine records as an
// escalation for the admin.
import type { JobState } from "./types";

export const JOB_STATES: readonly JobState[] = [
  "created",
  "funded",
  "offered",
  "accepted",
  "picked_up",
  "delivered",
  "confirmed",
  "verified",
  "settled",
  "rejected",
  "disputed",
] as const;

export const TERMINAL_STATES: readonly JobState[] = ["settled", "rejected", "disputed"];

// Legal forward moves. Anything not listed here is rejected by the engine, so
// the demo can never teleport a job past a control point (e.g. straight to
// `verified` without factory confirmation).
const TRANSITIONS: Record<JobState, readonly JobState[]> = {
  created: ["funded"],
  funded: ["offered"],
  offered: ["accepted", "created"], // "created" = ladder exhausted, requeue
  accepted: ["picked_up"],
  picked_up: ["delivered"],
  delivered: ["confirmed", "rejected"],
  confirmed: ["verified", "disputed"],
  verified: ["settled"],
  settled: [],
  rejected: [],
  disputed: [],
};

export function canTransition(from: JobState, to: JobState): boolean {
  return TRANSITIONS[from].includes(to);
}

export function isTerminal(state: JobState): boolean {
  return TERMINAL_STATES.includes(state);
}

/** The states a job can move to next, for driving the UI's action buttons. */
export function nextStates(from: JobState): readonly JobState[] {
  return TRANSITIONS[from];
}
