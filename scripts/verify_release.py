from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.integrity import cache_integrity_result, verify_release  # noqa: E402


def main() -> int:
    result = verify_release(ROOT, strict=False)
    cache_integrity_result(ROOT / "state", result)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
