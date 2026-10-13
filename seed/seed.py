"""Create SYNTHETIC farmers, transporters and factories. No real data.

Usage: python seed/seed.py [--out seed/out] [--seed 42] [--firestore]
Writes JSON files by default. --firestore also loads them (uses FIRESTORE_EMULATOR_HOST if set).
"""
import argparse
import json
import random
from pathlib import Path

DISTRICTS = {
    "Lahore": (31.52, 74.36),
    "Sheikhupura": (31.71, 73.98),
    "Kasur": (31.12, 74.45),
    "Faisalabad": (31.42, 73.08),
    "Okara": (30.81, 73.45),
}
RESIDUES = ["rice_straw", "wheat_straw", "cotton_stalk", "sugarcane_trash"]
FAKE_PHONE = "+92300000{:04d}"  # reserved-looking fake numbers


def jitter(rng: random.Random, lat: float, lon: float) -> tuple[float, float]:
    return round(lat + rng.uniform(-0.15, 0.15), 5), round(lon + rng.uniform(-0.15, 0.15), 5)


def make(rng: random.Random, n_farmers: int, n_transporters: int, n_factories: int) -> dict:
    districts = list(DISTRICTS)
    farmers, transporters, factories = [], [], []
    for i in range(n_farmers):
        d = rng.choice(districts)
        lat, lon = jitter(rng, *DISTRICTS[d])
        farmers.append({"id": f"farmer-{i:03d}", "name": f"Synthetic Farmer {i}", "phone": FAKE_PHONE.format(i),
                        "district": d, "village": f"Village {i}", "lat": lat, "lon": lon})
    for i in range(n_transporters):
        d = rng.choice(districts)
        lat, lon = jitter(rng, *DISTRICTS[d])
        transporters.append({"id": f"transporter-{i:03d}", "name": f"Synthetic Transporter {i}",
                             "phone": FAKE_PHONE.format(1000 + i), "tier": rng.choice([1, 2, 3]),
                             "approved": True, "lat": lat, "lon": lon})
    for i in range(n_factories):
        d = rng.choice(districts)
        lat, lon = jitter(rng, *DISTRICTS[d])
        factories.append({"id": f"factory-{i:03d}", "name": f"Synthetic Factory {i}",
                          "accepted_residues": rng.sample(RESIDUES, k=rng.randint(1, 3)),
                          "price_per_tonne_cents": rng.randint(4000, 9000), "lat": lat, "lon": lon})
    return {"farmers": farmers, "transporters": transporters, "factories": factories}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="seed/out")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--farmers", type=int, default=20)
    ap.add_argument("--transporters", type=int, default=8)
    ap.add_argument("--factories", type=int, default=4)
    ap.add_argument("--firestore", action="store_true")
    args = ap.parse_args()

    data = make(random.Random(args.seed), args.farmers, args.transporters, args.factories)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in data.items():
        (out / f"{name}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"{name}: {len(rows)}")

    if args.firestore:
        # TODO(F1): batch-write to Firestore collections farmers/transporters/factories.
        raise SystemExit("--firestore not implemented yet")


if __name__ == "__main__":
    main()
