"""Write the connector catalog to ``docs/connectors.json``.

The catalog is served live at ``GET /api/v1/integrations/connectors``; this keeps
the checked-in JSON in sync (same builder, so it cannot drift).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from voiceeval.services.connectors import build_catalog


def main() -> int:
    out = Path(__file__).resolve().parents[2] / "docs" / "connectors.json"
    out.write_text(json.dumps(build_catalog(), indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
