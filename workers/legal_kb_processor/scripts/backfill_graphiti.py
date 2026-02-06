"""
Backfill existing Legal KB entries to Graphiti as episodes (Phase 3).
Run from repo root with PYTHONPATH=workers/legal_kb_processor, or from workers/legal_kb_processor:
  python -m scripts.backfill_graphiti [--limit N] [--dry-run]

Requires: LEGAL_KB_ENABLE_GRAPHITI=yes, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FalkorDB/Neo4j config.
"""
import argparse
import logging
import sys
from pathlib import Path

# Allow importing legal_kb_processor when run as script
_worker_root = Path(__file__).resolve().parents[1]
if str(_worker_root) not in sys.path:
    sys.path.insert(0, str(_worker_root))

from supabase import create_client

from legal_kb_processor.config import (
    ENABLE_GRAPHITI,
    GRAPHITI_DATABASE,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)
from legal_kb_processor.graphiti_client import add_episode_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Backfill Legal KB to Graphiti")
    parser.add_argument("--limit", type=int, default=0, help="Max entries to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Do not add episodes, only list")
    args = parser.parse_args()

    if not ENABLE_GRAPHITI:
        logger.error("Set LEGAL_KB_ENABLE_GRAPHITI=yes to run backfill")
        sys.exit(1)
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    query = (
        supabase.table("legal_knowledge_base")
        .select("id, document_type, jurisdiction, summary, case_name, case_citation, court_name, decision_date, cited_cases, cited_statutes, title")
        .eq("is_active", True)
        .order("updated_at", desc=True)
    )
    if args.limit > 0:
        query = query.limit(args.limit)
    r = query.execute()

    rows = r.data or []
    logger.info("Found %d active Legal KB entries", len(rows))

    if args.dry_run:
        for row in rows:
            logger.info("Would add: id=%s title=%s jurisdiction=%s", row.get("id"), row.get("title"), row.get("jurisdiction"))
        return

    ok = 0
    fail = 0
    for row in rows:
        entry_id = str(row["id"])
        document_type = (row.get("document_type") or "document").strip()
        jurisdiction = (row.get("jurisdiction") or "").strip()
        summary = (row.get("summary") or "")[:500] if row.get("summary") else None
        case_name = row.get("case_name")
        decision_date = row.get("decision_date")
        cited_cases = list(row.get("cited_cases") or [])
        cited_statutes = list(row.get("cited_statutes") or [])
        citations = cited_cases + cited_statutes

        if add_episode_sync(
            entry_id=entry_id,
            document_type=document_type,
            jurisdiction=jurisdiction,
            summary=summary,
            case_name=case_name,
            citations=citations if citations else None,
            decision_date=str(decision_date) if decision_date else None,
        ):
            ok += 1
            logger.info("Added episode for entry %s (%s)", entry_id, row.get("title"))
        else:
            fail += 1
            logger.warning("Failed to add episode for entry %s", entry_id)

    logger.info("Backfill done: %d added, %d failed", ok, fail)
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
