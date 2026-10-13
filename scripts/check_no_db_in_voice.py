"""Fail if the voice project imports or depends on a database client.

Usage: python scripts/check_no_db_in_voice.py [voice_dir]
Scans every .py file's imports (AST) and the declared dependencies in pyproject.toml / requirements*.txt.
"""
import ast
import re
import sys
from pathlib import Path

FORBIDDEN = (
    "google.cloud.firestore",
    "google.cloud.datastore",
    "google.cloud.spanner",
    "google.cloud.bigtable",
    "google.cloud.sql",
    "firebase_admin",
    "firebase",
    "pyrebase",
    "sqlalchemy",
    "sqlite3",
    "psycopg",
    "psycopg2",
    "asyncpg",
    "pymysql",
    "mysql",
    "pymongo",
    "motor",
    "redis",
    "peewee",
    "tortoise",
    "databases",
)
FORBIDDEN_DEPS = {
    "google-cloud-firestore",
    "google-cloud-datastore",
    "google-cloud-spanner",
    "google-cloud-bigtable",
    "firebase-admin",
    "pyrebase4",
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "psycopg2-binary",
    "asyncpg",
    "pymysql",
    "pymongo",
    "motor",
    "redis",
    "peewee",
    "tortoise-orm",
    "databases",
}
SKIP_DIRS = {".venv", "venv", "__pycache__", "node_modules", ".git", "build", "dist"}


def is_forbidden(module: str) -> bool:
    return any(module == f or module.startswith(f + ".") for f in FORBIDDEN)


def imported_modules(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module
            for alias in node.names:  # `from google.cloud import firestore`
                yield node.lineno, f"{node.module}.{alias.name}"


def scan(root: Path) -> list[str]:
    problems: list[str] = []
    for path in root.rglob("*.py"):
        if SKIP_DIRS & set(path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as e:
            problems.append(f"{path}: cannot parse ({e})")
            continue
        for lineno, module in imported_modules(tree):
            if is_forbidden(module):
                problems.append(f"{path}:{lineno}: forbidden import '{module}'")
    for path in [root / "pyproject.toml", *root.glob("requirements*.txt")]:
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = re.match(r"""\s*["']?([A-Za-z0-9_.\-]+)""", line)
            if m and m.group(1).lower().replace("_", "-") in FORBIDDEN_DEPS:
                problems.append(f"{path}:{lineno}: forbidden dependency '{m.group(1)}'")
    return problems


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "voice"
    problems = scan(root)
    if problems:
        print("voice must not use a database client:")
        print("\n".join(problems))
        return 1
    print(f"ok: no database clients in {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
