"""Schema sanity that needs no database, plus DB-backed checks that skip without DATABASE_URL."""
import os

import pytest
from sqlalchemy import BigInteger, Float
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.db import async_url
from app.db_models import Base
from app.services.events import EVENT_TYPES, FakeEvents

MONEY_COLUMNS = {
    "factories": ["price_per_tonne"],
    "jobs": ["quoted_price_per_tonne"],
    "offers": ["payout_amount"],
    "ledger_entries": ["amount"],
    "products": ["unit_price"],
    "orders": ["total"],
    "sale_splits": ["amount"],
    "factory_candidates": ["price_per_tonne"],
}


def test_expected_tables_exist():
    assert {"users", "lots", "jobs", "offers", "ledger_entries", "sale_splits"} <= set(
        Base.metadata.tables
    )


def test_money_is_integer_minor_units_never_float():
    for table, cols in MONEY_COLUMNS.items():
        for col in cols:
            col_type = Base.metadata.tables[table].c[col].type
            assert isinstance(col_type, BigInteger), f"{table}.{col}"
            assert not isinstance(col_type, Float)


def test_ledger_has_no_updated_at_it_is_append_only():
    assert "updated_at" not in Base.metadata.tables["ledger_entries"].c


def test_status_columns_have_check_constraints():
    ddl = str(CreateTable(Base.metadata.tables["jobs"]).compile(dialect=postgresql.dialect()))
    assert "'settled'" in ddl and "'disputed'" in ddl


def test_async_url_normalises_driver():
    assert async_url("postgresql://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert async_url("postgres://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert async_url("postgresql+asyncpg://u:p@h/db").startswith("postgresql+asyncpg://")


async def test_fake_events_records_publishes():
    sink = FakeEvents()
    await sink.publish("job.updated", job_id="j1")
    assert sink.sent == [{"type": "job.updated", "job_id": "j1"}]
    assert "job.updated" in EVENT_TYPES


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
async def test_database_is_reachable_and_migrated():
    from sqlalchemy import text

    from app.db import get_engine

    async with get_engine().connect() as conn:
        tables = (
            await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            )
        ).scalars().all()
    assert "ledger_entries" in tables, "run `alembic upgrade head` first"


# --- DB-backed invariants (skip without DATABASE_URL; each test rolls back) --------------------

needs_db = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture
async def conn():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import get_settings

    engine = create_async_engine(async_url(get_settings().database_url), poolclass=NullPool)
    async with engine.connect() as c:
        trans = await c.begin()
        yield c
        await trans.rollback()
    await engine.dispose()


async def _job(conn):
    from sqlalchemy import text

    fid = (await conn.execute(text(
        "INSERT INTO factories (name, lat, lon, price_per_tonne) "
        "VALUES ('t', 0, 0, 1) RETURNING id"
    ))).scalar()
    farmer = (await conn.execute(text(
        "INSERT INTO farmers (phone) VALUES ('+920000000001') RETURNING id"
    ))).scalar()
    await conn.execute(
        text("INSERT INTO residue_types VALUES ('x_test', 'X') ON CONFLICT DO NOTHING")
    )
    lot = (await conn.execute(text(
        "INSERT INTO lots (farmer_id, residue_code, quantity_tonnes, lat, lon) "
        "VALUES (:f, 'x_test', 1, 0, 0) RETURNING id"), {"f": farmer})).scalar()
    return (await conn.execute(text(
        "INSERT INTO jobs (lot_id, factory_id, quoted_price_per_tonne, farmer_share_bps, "
        "est_weight_kg) VALUES (:l, :f, 1, 5000, 1000) RETURNING id"),
        {"l": lot, "f": fid})).scalar()


@needs_db
async def test_ledger_is_append_only_in_the_database(conn):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    job = await _job(conn)
    await conn.execute(text(
        "INSERT INTO ledger_entries (job_id, kind, amount) VALUES (:j, 'escrow_in', 100)"),
        {"j": job})
    with pytest.raises(DBAPIError, match="append-only"):
        async with conn.begin_nested():
            await conn.execute(text("UPDATE ledger_entries SET amount = 1"))
    with pytest.raises(DBAPIError, match="append-only"):
        async with conn.begin_nested():
            await conn.execute(text("DELETE FROM ledger_entries"))


@needs_db
async def test_ledger_balance_view(conn):
    from sqlalchemy import text

    job = await _job(conn)
    for kind, amt in [("escrow_in", 1000), ("release_farmer", 600), ("platform_fee", 100)]:
        await conn.execute(text(
            "INSERT INTO ledger_entries (job_id, kind, amount) VALUES (:j, :k, :a)"),
            {"j": job, "k": kind, "a": amt})
    row = (await conn.execute(text(
        "SELECT escrow_in, paid_out, balanced FROM ledger_balance WHERE job_id = :j"),
        {"j": job})).one()
    assert (row.escrow_in, row.paid_out, row.balanced) == (1000, 700, False)
    await conn.execute(text(
        "INSERT INTO ledger_entries (job_id, kind, amount) "
        "VALUES (:j, 'release_transporter', 300)"),
        {"j": job})
    assert (await conn.execute(text(
        "SELECT balanced FROM ledger_balance WHERE job_id = :j"), {"j": job})).scalar() is True


@needs_db
async def test_only_one_offer_can_be_accepted_per_job(conn):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    job = await _job(conn)
    tids = []
    for i in range(2):
        tids.append((await conn.execute(text(
            "INSERT INTO transporters (phone, lat, lon) VALUES (:p, 0, 0) RETURNING id"),
            {"p": f"+9200000009{i}"})).scalar())
    for seq, tid in enumerate(tids):
        await conn.execute(text(
            "INSERT INTO offers (job_id, transporter_id, sequence, expires_at, status, "
            "payout_amount) VALUES (:j, :t, :s, now(), 'pending', 1)"),
            {"j": job, "t": tid, "s": seq})
    accept = "UPDATE offers SET status = 'accepted' WHERE job_id = :j AND sequence = :s"
    await conn.execute(text(accept), {"j": job, "s": 0})
    with pytest.raises(IntegrityError):
        async with conn.begin_nested():
            await conn.execute(text(accept), {"j": job, "s": 1})


@needs_db
async def test_negative_money_is_rejected(conn):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    job = await _job(conn)
    with pytest.raises(IntegrityError):
        async with conn.begin_nested():
            await conn.execute(text(
                "INSERT INTO ledger_entries (job_id, kind, amount) VALUES (:j, 'refund', -1)"),
                {"j": job})
