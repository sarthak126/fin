from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
load_dotenv(BACKEND_ROOT / ".env")

from core.database import db, ensure_runtime_schema_compatibility  # noqa: E402
from services.retention_service import enforce_retention_policy  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply configured ArgentNorth retention windows for cases, documents, "
            "derived artifacts, vectors, job manifests, and audit logs."
        )
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print indented JSON output.",
    )
    return parser


async def _main() -> int:
    args = _build_parser().parse_args()

    await db.connect()
    try:
        await ensure_runtime_schema_compatibility(db)
        summary = await enforce_retention_policy(db)
        print(json.dumps(summary.model_dump(), indent=2 if args.pretty else None))
        return 0
    finally:
        await db.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
