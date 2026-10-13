"""Write the OpenAPI spec to a file (default: openapi.json). Used by web `npm run gen:api`."""
import json
import sys
from pathlib import Path

from app.main import app

out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print(f"wrote {out}")
