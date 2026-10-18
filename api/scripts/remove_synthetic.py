"""Remove the synthetic accounts that `seed/seed.py` loads (dev-* users, Synthetic Farmers,
Transporters and Factories, their residues and products) from a database. Villages and residue
types (reference data) stay.

    cd api
    python -m scripts.remove_synthetic                     # preview: counts and blockers
    python -m scripts.remove_synthetic --apply             # delete, in one transaction
    python -m scripts.remove_synthetic --rerank [--apply]  # first move unfunded jobs off
                                                           # synthetic factories

Uses DATABASE_URL (environment first, then api/.env). Refuses to delete while real records still
point at a synthetic row (a lot, job, offer, order, ledger entry, event...), and lists them, because
deleting those would rewrite real history. `--rerank` ranks lots whose job is still `created`
(unfunded) again among the real factories, with the app's own `reassign_lot`. Per-person
notification copies addressed to a dev-* user, and factory rankings that did not choose a
synthetic factory, are removed with the accounts. A preview always rolls back.
"""
import argparse
import asyncio
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_engine
from app.services.assignment_store import reassign_lot

NS = uuid.UUID("6f1d2a52-5b5e-4c0e-9d61-0a7d0f5a1c11")  # same namespace as seed/seed.py


def sid(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{key}"))


# Enough to cover any seed run (defaults are 20 farmers, 8 transporters, 4 factories).
FARMERS = [sid("farmer", str(i)) for i in range(200)]
TRANSPORTERS = [sid("transporter", str(i)) for i in range(100)]
FACTORIES = [sid("factory", str(i)) for i in range(50)]
DEV_UIDS = (
    "uid = 'dev-admin' OR uid LIKE 'dev-buyer-%' OR uid LIKE 'dev-transporter-%' "
    "OR uid LIKE 'dev-factory-%'"
)

# Rows that belong to the synthetic accounts themselves and go with them.
OWNED = {
    ("farmers", "user_uid"), ("transporters", "user_uid"), ("factories", "user_uid"),
    ("factory_residues", "factory_id"), ("products", "factory_id"),
    ("notifications", "recipient_uid"), ("factory_candidates", "factory_id"),
}
SETS = {
    "users": "SELECT uid FROM syn_users",
    "farmers": "SELECT id FROM syn_farmers",
    "transporters": "SELECT id FROM syn_transporters",
    "factories": "SELECT id FROM syn_factories",
    "products": "SELECT id FROM syn_products",
}
DELETES = [
    "DELETE FROM notifications WHERE recipient_uid IN (SELECT uid FROM syn_users)",
    "DELETE FROM factory_candidates WHERE factory_id IN (SELECT id FROM syn_factories)",
    "DELETE FROM factory_residues WHERE factory_id IN (SELECT id FROM syn_factories)",
    "DELETE FROM products WHERE id IN (SELECT id FROM syn_products)",
    "DELETE FROM factories WHERE id IN (SELECT id FROM syn_factories)",
    "DELETE FROM transporters WHERE id IN (SELECT id FROM syn_transporters)",
    "DELETE FROM farmers WHERE id IN (SELECT id FROM syn_farmers)",
    "DELETE FROM users WHERE uid IN (SELECT uid FROM syn_users)",
]


class Rollback(Exception):
    """Ends a preview or a refused run: the transaction rolls back, nothing changes."""


async def _mark(conn) -> None:
    """Temp tables holding the synthetic keys, dropped at the end of the transaction."""
    await conn.execute(text(
        "CREATE TEMP TABLE syn_users ON COMMIT DROP AS SELECT uid FROM users WHERE " + DEV_UIDS
    ))
    await conn.execute(text(
        "CREATE TEMP TABLE syn_farmers ON COMMIT DROP AS SELECT id FROM farmers "
        "WHERE id = ANY(CAST(:ids AS uuid[]))"
    ), {"ids": FARMERS})
    await conn.execute(text(
        "CREATE TEMP TABLE syn_transporters ON COMMIT DROP AS SELECT id FROM transporters "
        "WHERE id = ANY(CAST(:ids AS uuid[])) OR user_uid IN (SELECT uid FROM syn_users)"
    ), {"ids": TRANSPORTERS})
    await conn.execute(text(
        "CREATE TEMP TABLE syn_factories ON COMMIT DROP AS SELECT id FROM factories "
        "WHERE id = ANY(CAST(:ids AS uuid[])) OR user_uid IN (SELECT uid FROM syn_users)"
    ), {"ids": FACTORIES})
    await conn.execute(text(
        "CREATE TEMP TABLE syn_products ON COMMIT DROP AS SELECT id FROM products "
        "WHERE factory_id IN (SELECT id FROM syn_factories)"
    ))


async def _rerank(conn) -> None:
    """Synthetic factories stop accepting residues, then each unfunded job on one is re-ranked."""
    await conn.execute(text(
        "DELETE FROM factory_residues WHERE factory_id IN (SELECT id FROM syn_factories)"
    ))
    lots = (await conn.execute(text(
        "SELECT lot_id FROM jobs WHERE state = 'created' "
        "AND factory_id IN (SELECT id FROM syn_factories)"
    ))).scalars().all()
    session = AsyncSession(bind=conn)  # joins this transaction; only flushes, never commits
    for lot_id in lots:
        job, _ = await reassign_lot(session, lot_id)
        name = None
        if job is not None:
            name = (await conn.execute(
                text("SELECT name FROM factories WHERE id = :id"), {"id": job.factory_id}
            )).scalar_one()
        print(f"  lot {lot_id}: " + (f"now at {name}" if name else "no factory accepts it, open"))
    await session.flush()


async def _blockers(conn) -> list[str]:
    fks = (await conn.execute(text("""
        SELECT tc.table_name, kcu.column_name, ccu.table_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
          AND ccu.table_name IN ('users', 'farmers', 'transporters', 'factories', 'products')
    """))).all()
    found = []
    for table, column, target in fks:
        if (table, column) in OWNED:
            continue
        n = (await conn.execute(text(
            f'SELECT count(*) FROM "{table}" WHERE "{column}" IN ({SETS[target]})'
        ))).scalar_one()
        if n:
            found.append(f"  {table}.{column} -> {target}: {n} row(s)")
    chosen = (await conn.execute(text(
        "SELECT count(*) FROM factory_candidates WHERE chosen "
        "AND factory_id IN (SELECT id FROM syn_factories)"
    ))).scalar_one()
    if chosen:
        found.append(f"  factory_candidates: {chosen} lot(s) chose a synthetic factory")
    return found


async def run(apply: bool, rerank: bool) -> int:
    try:
        async with get_engine().begin() as conn:
            await _mark(conn)
            print("Synthetic rows found:")
            for name, query in SETS.items():
                n = (await conn.execute(text(f"SELECT count(*) FROM ({query}) s"))).scalar_one()
                print(f"  {name}: {n}")
            if rerank:
                print("\nRe-ranking unfunded jobs at synthetic factories:")
                await _rerank(conn)
            blockers = await _blockers(conn)
            if blockers:
                print("\nReal records still point at synthetic rows; nothing was deleted:")
                print("\n".join(blockers))
                print("Move or remove those first (--rerank moves jobs that are not funded yet).")
                raise Rollback(1)
            print("\nNo blockers.")
            if not apply:
                raise Rollback(0)
            for sql in DELETES:
                result = await conn.execute(text(sql))
                print(f"  {sql.split(' WHERE')[0]}: {result.rowcount}")
            print("Deleted.")
            return 0
    except Rollback as stop:
        if not stop.args[0]:
            print("Preview only: rolled back. Run again with --apply to delete.")
        return stop.args[0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="delete (default: preview only)")
    ap.add_argument("--rerank", action="store_true", help="move unfunded jobs to real factories")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(args.apply, args.rerank)))


if __name__ == "__main__":
    main()
