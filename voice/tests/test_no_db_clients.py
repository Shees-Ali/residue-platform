import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_no_db_in_voice.py"
VOICE = Path(__file__).resolve().parents[1]


def run(target: Path) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), str(target)]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_voice_has_no_db_clients():
    assert run(VOICE).returncode == 0


def test_check_catches_firestore_import(tmp_path):
    (tmp_path / "bad.py").write_text("from google.cloud import firestore\n")
    r = run(tmp_path)
    assert r.returncode == 1 and "firestore" in r.stdout
