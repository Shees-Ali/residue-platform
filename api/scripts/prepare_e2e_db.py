"""Make a clean throwaway database for the browser end-to-end tests (web: npm run e2e).

    python -m scripts.prepare_e2e_db

Reads DATABASE_URL (api/.env), takes its server and login, and (re)creates a database called
`residue_e2e` there with the migrations applied and only the reference data (villages and residue
types) in it: no accounts, no factories, so the test creates exactly the people it needs. The
real `residue` database is never touched. Prints the name of the new database.
"""
import asyncio
import os
import random
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

ROOT = Path(__file__).resolve().parents[2]
NAME = "residue_e2e"


def e2e_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{NAME}", scheme="postgresql"))


async def recreate(admin_url: str) -> None:
    conn = await asyncpg.connect(admin_url)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{NAME}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{NAME}"')
    finally:
        await conn.close()


async def load_reference(url: str) -> None:
    sys.path.insert(0, str(ROOT / "seed"))
    import seed  # noqa: PLC0415
    from sqlalchemy.dialects.postgresql import insert  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from app.db import async_url  # noqa: PLC0415
    from app.db_models import tables as t  # noqa: PLC0415

    rows = seed.make(random.Random(42), 0, 0, 0)
    engine = create_async_engine(async_url(url))
    async with engine.begin() as conn:
        for name, model in (("residue_types", t.ResidueType), ("villages", t.Village)):
            await conn.execute(insert(model).values(rows[name]).on_conflict_do_nothing())
    await engine.dispose()


def target_url() -> str:
    """The e2e database's URL, from DATABASE_URL (api/.env). Imports nothing from the app."""
    from dotenv import load_dotenv  # noqa: PLC0415

    load_dotenv(ROOT / "api" / ".env")
    url = os.environ["DATABASE_URL"]
    if urlsplit(url).path.strip("/") == NAME:
        raise SystemExit("DATABASE_URL already points at the e2e database; refusing to continue")
    return e2e_url(url)


def prepare() -> str:
    """Recreate the e2e database, migrate it, load reference data; return its URL."""
    target = target_url()
    parts = urlsplit(os.environ["DATABASE_URL"])
    asyncio.run(recreate(urlunsplit(parts._replace(path="/postgres", scheme="postgresql"))))
    env = {**os.environ, "DATABASE_URL": target}
    migrate = [sys.executable, "-m", "alembic", "upgrade", "head"]
    subprocess.run(migrate, cwd=ROOT / "api", env=env, check=True, capture_output=True)
    asyncio.run(load_reference(target))
    return target


def main() -> None:
    prepare()
    print(f"ready: database {NAME}")  # never print the URL: it holds the password


if __name__ == "__main__":
    main()
