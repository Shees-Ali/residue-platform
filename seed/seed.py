"""Load SYNTHETIC reference data into Postgres. No real data, ever.

Usage (from the repo root, DATABASE_URL set in api/.env or the environment):
    python seed/seed.py                # insert, safe to re-run (rows have fixed ids)
    python seed/seed.py --dry-run      # build the rows and print counts, no database needed

Run `alembic upgrade head` in api/ first. Deterministic for a given --seed.
"""
import argparse
import asyncio
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from app.services.places import DISTRICTS, VILLAGES  # noqa: E402

RESIDUES = {
    "rice_straw": "Rice straw",
    "wheat_straw": "Wheat straw",
    "cotton_stalk": "Cotton stalk",
    "sugarcane_trash": "Sugarcane trash",
}
PRODUCT_NAMES = ["Biomass pellets", "Compressed briquettes", "Compost"]
FAKE_PHONE = "+92300000{:04d}"  # fake numbers, never real
NS = uuid.UUID("6f1d2a52-5b5e-4c0e-9d61-0a7d0f5a1c11")  # fixed namespace for deterministic ids


def sid(kind: str, key: str) -> uuid.UUID:
    return uuid.uuid5(NS, f"{kind}:{key}")


def jitter(rng: random.Random, lat: float, lon: float) -> tuple[float, float]:
    return round(lat + rng.uniform(-0.15, 0.15), 5), round(lon + rng.uniform(-0.15, 0.15), 5)


def make(rng: random.Random, n_farmers: int, n_transporters: int, n_factories: int) -> dict:
    """Return rows per table. Money is integer minor units (paisa)."""
    districts = list(DISTRICTS)
    rows: dict[str, list[dict]] = {
        "residue_types": [{"code": c, "label": label} for c, label in RESIDUES.items()],
        "users": [
            {"uid": "dev-admin", "role": "admin", "display_name": "Dev Admin"},
            {"uid": "dev-buyer-0", "role": "buyer", "display_name": "Dev Buyer"},
        ],
        "villages": [], "farmers": [], "transporters": [],
        "factories": [], "factory_residues": [], "products": [],
    }
    for district, villages in VILLAGES.items():
        clat, clon = DISTRICTS[district]
        for name, (dlat, dlon) in villages.items():
            rows["villages"].append(
                {"id": sid("village", f"{district}:{name}"), "name": name, "district": district,
                 "lat": round(clat + dlat, 5), "lon": round(clon + dlon, 5)}
            )
    for i in range(n_farmers):
        village = rng.choice(rows["villages"])
        rows["farmers"].append(
            {"id": sid("farmer", str(i)), "name": f"Synthetic Farmer {i}",
             "phone": FAKE_PHONE.format(i), "village_id": village["id"]}
        )
    for i in range(n_transporters):
        lat, lon = jitter(rng, *DISTRICTS[rng.choice(districts)])
        rows["users"].append(
            {"uid": f"dev-transporter-{i}", "role": "transporter",
             "display_name": f"Dev Transporter {i}"}
        )
        rows["transporters"].append(
            {"id": sid("transporter", str(i)), "phone": FAKE_PHONE.format(1000 + i),
             "user_uid": f"dev-transporter-{i}",
             "tier": rng.choice([1, 2, 3]), "max_tonnes": rng.choice([3, 5, 10]),
             "lat": lat, "lon": lon, "approved": True}
        )
    for i in range(n_factories):
        lat, lon = jitter(rng, *DISTRICTS[rng.choice(districts)])
        factory_id = sid("factory", str(i))
        rows["users"].append(
            {"uid": f"dev-factory-{i}", "role": "factory", "display_name": f"Dev Factory {i}"}
        )
        rows["factories"].append(
            {"id": factory_id, "name": f"Synthetic Factory {i}", "user_uid": f"dev-factory-{i}",
             "lat": lat, "lon": lon,
             "price_per_tonne": rng.randint(400_000, 900_000)}  # paisa
        )
        for code in rng.sample(list(RESIDUES), k=rng.randint(1, 3)):
            rows["factory_residues"].append({"factory_id": factory_id, "residue_code": code})
        for j, name in enumerate(PRODUCT_NAMES):
            rows["products"].append(
                {"id": sid("product", f"{i}-{j}"), "factory_id": factory_id, "name": name,
                 "unit_price": rng.randint(5_000, 40_000), "stock": rng.randint(50, 500)}
            )
    return rows


async def load(rows: dict) -> None:
    from datetime import UTC, datetime

    from sqlalchemy.dialects.postgresql import insert

    from app.db import get_engine
    from app.db_models import tables as t

    order = [
        ("users", t.User), ("residue_types", t.ResidueType), ("villages", t.Village), ("farmers", t.Farmer),
        ("transporters", t.Transporter), ("factories", t.Factory),
        ("factory_residues", t.FactoryResidue), ("products", t.Product),
    ]
    async with get_engine().begin() as conn:
        for name, model in order:
            data = rows[name]
            if name == "transporters":
                now = datetime.now(UTC)
                data = [
                    {**{k: v for k, v in r.items() if k != "approved"},
                     "approved_at": now if r["approved"] else None}
                    for r in data
                ]
            if data:
                stmt = insert(model).values(data)
                if name in ("factories", "transporters"):
                    # rows seeded before users existed get linked on re-run
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["id"], set_={"user_uid": stmt.excluded.user_uid}
                    )
                else:
                    stmt = stmt.on_conflict_do_nothing()
                await conn.execute(stmt)
            print(f"{name}: {len(data)}")
    await get_engine().dispose()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--farmers", type=int, default=20)
    ap.add_argument("--transporters", type=int, default=8)
    ap.add_argument("--factories", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true", help="build rows, print counts, skip the DB")
    args = ap.parse_args()

    rows = make(random.Random(args.seed), args.farmers, args.transporters, args.factories)
    if args.dry_run:
        for name, data in rows.items():
            print(f"{name}: {len(data)} (dry run)")
        return
    asyncio.run(load(rows))


if __name__ == "__main__":
    main()
