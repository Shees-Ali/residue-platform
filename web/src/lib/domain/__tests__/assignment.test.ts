// A1 tests-first: factory scoring, mirrored from api/tests/test_assignment.py.
// Failing by design until assignment.ts is implemented (see memory/decisions.md:
// the same invariants are tested in both projects so the demo engine and the
// future API produce identical rankings).
import { describe, expect, test } from "vitest";
import { haversineKm, rankFactories, scoreFactory } from "../assignment";
import type { Factory, LotRequest, ResidueType } from "../types";

const LOT: LotRequest = { residueType: "rice_straw", lat: 31.5, lon: 74.3, quantityTonnes: 10 };

function fac(
  id: string,
  residues: ResidueType[],
  lat: number,
  lon: number,
  price: number,
): Factory {
  return { id, name: id, acceptedResidues: residues, lat, lon, pricePerTonneCents: price };
}

describe("A1 assignment", () => {
  test("haversine zero and known distance", () => {
    expect(haversineKm(31.5, 74.3, 31.5, 74.3)).toBeCloseTo(0, 5);
    expect(haversineKm(0, 0, 0, 1)).toBeCloseTo(111.19, 1);
  });

  test("factory not accepting residue is ineligible", () => {
    expect(scoreFactory(fac("f", ["wheat_straw"], 31.5, 74.3, 100), LOT)).toBeNull();
  });

  test("closer factory scores higher at equal price", () => {
    const near = fac("n", ["rice_straw"], 31.51, 74.31, 100);
    const far = fac("f", ["rice_straw"], 32.5, 75.3, 100);
    expect(scoreFactory(near, LOT)!).toBeGreaterThan(scoreFactory(far, LOT)!);
  });

  test("higher price scores higher at equal distance", () => {
    const cheap = fac("c", ["rice_straw"], 31.6, 74.4, 100);
    const rich = fac("r", ["rice_straw"], 31.6, 74.4, 200);
    expect(scoreFactory(rich, LOT)!).toBeGreaterThan(scoreFactory(cheap, LOT)!);
  });

  test("rank drops ineligible and orders best first", () => {
    const a = fac("a", ["rice_straw"], 31.51, 74.31, 100);
    const b = fac("b", ["wheat_straw"], 31.5, 74.3, 999);
    const c = fac("c", ["rice_straw"], 33.0, 75.0, 100);
    expect(rankFactories([c, b, a], LOT).map((r) => r.factory.id)).toEqual(["a", "c"]);
  });
});
