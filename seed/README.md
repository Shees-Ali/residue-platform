# seed

Synthetic reference data (residue types, villages, farmers, transporters, factories, products) loaded into Postgres. No real data, ever.

```
cd api && alembic upgrade head      # once, creates the tables
python seed/seed.py                 # from the repo root; needs DATABASE_URL (api/.env)
python seed/seed.py --dry-run       # print row counts only, no database
```

Rows have fixed ids (uuid5), so re-running is safe and changes nothing. Money is integer paisa. Phone numbers are fake.
