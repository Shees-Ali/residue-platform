"""Seed rows must fit the tables (no database needed)."""
import importlib.util
import random
from pathlib import Path

from app.db_models import tables as t

spec = importlib.util.spec_from_file_location(
    "seed_module", Path(__file__).resolve().parents[2] / "seed" / "seed.py"
)
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)

MODELS = {
    "residue_types": t.ResidueType, "villages": t.Village, "farmers": t.Farmer,
    "transporters": t.Transporter, "factories": t.Factory,
    "factory_residues": t.FactoryResidue, "products": t.Product,
}


def test_seed_rows_only_use_real_columns():
    rows = seed.make(random.Random(1), 5, 3, 2)
    for name, model in MODELS.items():
        cols = set(model.__table__.c.keys())
        for row in rows[name]:
            extra = set(row) - cols - ({"approved"} if name == "transporters" else set())
            assert not extra, f"{name}: {extra}"


def test_seed_is_deterministic_and_synthetic():
    a = seed.make(random.Random(7), 4, 2, 2)
    b = seed.make(random.Random(7), 4, 2, 2)
    assert a == b
    assert all(f["phone"].startswith("+92300000") for f in a["farmers"])
    assert all(isinstance(f["price_per_tonne"], int) for f in a["factories"])
