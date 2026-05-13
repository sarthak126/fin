from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_ROOT))
load_dotenv(BACKEND_ROOT / ".env")

from core.database import db, ensure_runtime_schema_compatibility  # noqa: E402
from services.bank_statement_reanalysis_service import (  # noqa: E402
    rerun_bank_statement_documents,
    select_bank_statement_documents,
)


def _flatten(values: list[list[str]] | None) -> list[str]:
    flattened: list[str] = []
    for group in values or []:
        flattened.extend(group)
    return flattened


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Force-rerun bank-statement analyses, create fresh analysis rows, "
            "refresh provisional case snapshots, and invalidate finalized case snapshots."
        )
    )
    parser.add_argument(
        "--document-id",
        dest="document_ids",
        action="append",
        nargs="+",
        help="One or more document ids to rerun.",
    )
    parser.add_argument(
        "--case-id",
        dest="case_ids",
        action="append",
        nargs="+",
        help="One or more case ids (or legacy source document ids) whose bank statements should be rerun.",
    )
    parser.add_argument(
        "--org-id",
        dest="org_ids",
        action="append",
        nargs="+",
        help="Restrict selection to one or more org ids.",
    )
    parser.add_argument(
        "--all-bank-statements",
        action="store_true",
        help="Explicitly allow rerunning every bank-statement document that matches the optional org filter.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on the number of matched documents to rerun.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the matching documents without rerunning analysis.",
    )
    return parser


async def _main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    document_ids = _flatten(args.document_ids)
    case_ids = _flatten(args.case_ids)
    org_ids = _flatten(args.org_ids)

    if not (document_ids or case_ids or args.all_bank_statements):
        parser.error(
            "Provide at least one --document-id, --case-id, or --all-bank-statements selector."
        )

    await db.connect()
    try:
        await ensure_runtime_schema_compatibility(db)
        documents = await select_bank_statement_documents(
            db=db,
            document_ids=document_ids,
            case_ids=case_ids,
            org_ids=org_ids,
            limit=args.limit,
        )
        if args.dry_run:
            preview = [
                {
                    "document_id": getattr(document, "id", None),
                    "case_id": getattr(document, "case_id", None),
                    "org_id": getattr(document, "org_id", None),
                    "status": getattr(document, "status", None),
                    "original_filename": getattr(document, "original_filename", None),
                }
                for document in documents
            ]
            print(json.dumps({"matched_documents": len(preview), "documents": preview}, indent=2))
            return 0

        results = await rerun_bank_statement_documents(
            db=db,
            documents=documents,
        )
        print(
            json.dumps(
                {
                    "matched_documents": len(documents),
                    "reprocessed_documents": len(results),
                    "results": [result.as_dict() for result in results],
                },
                indent=2,
            )
        )
        return 0
    finally:
        if db.is_connected():
            await db.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
