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

from core.config import get_settings  # noqa: E402
from core.database import db  # noqa: E402
from services.production_readiness_service import build_readiness_report  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run ArgentNorth production readiness checks and exit non-zero on failures."
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Skip live database/audit checks.",
    )
    parser.add_argument(
        "--include-storage",
        action="store_true",
        help="Run a live S3/KMS document/password round-trip.",
    )
    parser.add_argument(
        "--include-clerk",
        action="store_true",
        help="Fetch Clerk JWKS with the configured Clerk secret.",
    )
    parser.add_argument(
        "--allow-non-production-env",
        action="store_true",
        help="Warn instead of failing when APP_ENV is not production.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print indented JSON output.",
    )
    return parser


async def _main() -> int:
    args = _build_parser().parse_args()
    settings = get_settings()
    include_live_db = not args.static_only

    if include_live_db:
        await db.connect()

    try:
        report = await build_readiness_report(
            settings=settings,
            db=db if include_live_db else None,
            include_live_db=include_live_db,
            include_storage=args.include_storage,
            include_clerk=args.include_clerk,
            require_production_env=not args.allow_non_production_env,
        )
        print(json.dumps(report.model_dump(), indent=2 if args.pretty else None))
        return report.exit_code()
    finally:
        if include_live_db:
            await db.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
