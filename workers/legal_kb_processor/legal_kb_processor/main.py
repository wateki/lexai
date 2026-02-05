"""
Legal KB processor worker: full Docling + PageIndex pipeline with metadata extraction,
citation parsing, optional embedding, and optional Graphiti episode.
"""
import argparse
import logging
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from supabase import create_client

from .citations import parse_citations
from .config import (
    DOCLING_MAX_RETRIES,
    ENABLE_VECTOR_FALLBACK,
    LEGAL_KB_BUCKET,
    LOG_LEVEL,
    MAX_TEXT_FOR_EMBEDDING,
    OPENAI_API_KEY,
    PAGEINDEX_ADD_NODE_SUMMARY,
    PIPELINE_NAME,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)
from .embeddings import generate_embedding
from .extraction import extract_legal_metadata
from .graphiti_client import add_episode_sync
from .pipeline import run_docling, run_pageindex_from_markdown, tree_depth_and_count

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def get_supabase():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def poll_one_job(supabase):
    """Fetch one queued job; mark as processing and return (job, entry_id)."""
    r = (
        supabase.table("legal_kb_processing_jobs")
        .select("id, entry_id, organization_id, storage_bucket, storage_path, attempts, payload")
        .eq("status", "queued")
        .eq("pipeline", PIPELINE_NAME)
        .order("created_at", desc=False)
        .limit(1)
        .execute()
    )
    if not r.data or len(r.data) == 0:
        return None, None

    job = r.data[0]
    job_id = job["id"]
    entry_id = job["entry_id"]

    supabase.table("legal_kb_processing_jobs").update({
        "status": "processing",
        "attempts": job.get("attempts", 0) + 1,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }).eq("id", job_id).execute()

    supabase.table("legal_knowledge_base").update({
        "processing_status": "processing",
    }).eq("id", entry_id).execute()

    return job, entry_id


def download_file(supabase, bucket: str, path: str) -> bytes:
    return supabase.storage.from_(bucket).download(path)


def _get_existing_entry(supabase, entry_id: str) -> dict | None:
    r = supabase.table("legal_knowledge_base").select(
        "title, summary, document_type, jurisdiction, case_name, case_citation, court_name, "
        "decision_date, statute_name, statute_number, practice_areas, keywords, key_points, legal_principles"
    ).eq("id", entry_id).single().execute()
    if r.data:
        return r.data
    return None


def process_job(supabase, job: dict, entry_id: str) -> None:
    bucket = job.get("storage_bucket") or LEGAL_KB_BUCKET
    path = job["storage_path"]
    job_id = job["id"]
    payload = job.get("payload") or {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(path).suffix or ".pdf") as f:
        f.write(download_file(supabase, bucket, path))
        file_path = f.name

    try:
        # --- 1) Docling (with retries) ---
        last_docling_error = None
        for attempt in range(DOCLING_MAX_RETRIES + 1):
            try:
                markdown_text, docling_json = run_docling(file_path)
                break
            except Exception as e:
                last_docling_error = e
                logger.warning("Docling attempt %s failed: %s", attempt + 1, e)
                if attempt < DOCLING_MAX_RETRIES:
                    time.sleep(2)
        else:
            raise RuntimeError(f"Docling failed after {DOCLING_MAX_RETRIES + 1} attempts: {last_docling_error}")

        supabase.table("legal_knowledge_base").update({
            "docling_markdown": markdown_text,
            "docling_json": docling_json,
            "processing_status": "docling_complete",
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", entry_id).execute()

        # --- 2) PageIndex tree ---
        add_summary = PAGEINDEX_ADD_NODE_SUMMARY and bool(OPENAI_API_KEY)
        tree_result = run_pageindex_from_markdown(markdown_text, add_summary=add_summary)
        depth, count = tree_depth_and_count(tree_result)
        pageindex_metadata = {
            "tree_depth": depth,
            "node_count": count,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        # --- 3) Existing row + LLM metadata extraction ---
        existing = _get_existing_entry(supabase, entry_id) or {}
        existing.update(payload)
        docling_sections = None
        if isinstance(docling_json, dict):
            docling_sections = docling_json.get("export_format", {}).get("items") or docling_json.get("items")
        extracted = extract_legal_metadata(
            markdown_text,
            existing=existing,
            docling_sections_hint=docling_sections if isinstance(docling_sections, list) else None,
        )

        # --- 4) Citation parsing (eyecite from local repo) ---
        cited_cases, cited_statutes = parse_citations(markdown_text)

        # --- 5) Optional embedding ---
        ai_embedding = None
        if ENABLE_VECTOR_FALLBACK and OPENAI_API_KEY:
            text_for_embedding = (extracted.get("summary") or markdown_text)[:MAX_TEXT_FOR_EMBEDDING]
            ai_embedding = generate_embedding(text_for_embedding, max_chars=MAX_TEXT_FOR_EMBEDDING)

        # --- 6) Optional Graphiti episode ---
        add_episode_sync(
            entry_id=entry_id,
            document_type=extracted.get("document_type") or existing.get("document_type") or "legal_article",
            jurisdiction=extracted.get("jurisdiction") or existing.get("jurisdiction") or "",
            summary=extracted.get("summary"),
            case_name=extracted.get("case_name") or existing.get("case_name"),
            citations=cited_cases + cited_statutes,
            decision_date=extracted.get("decision_date") or (str(existing.get("decision_date")) if existing.get("decision_date") else None),
        )

        # --- 7) Final DB update ---
        update_payload = {
            "pageindex_tree": tree_result,
            "pageindex_metadata": pageindex_metadata,
            "processing_status": "completed",
            "processing_pipeline": PIPELINE_NAME,
            "ai_processed": True,
            "full_text": markdown_text[:50000],
            "cited_cases": cited_cases if cited_cases else None,
            "cited_statutes": cited_statutes if cited_statutes else None,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        if extracted.get("title") and not (existing.get("title") or "").strip():
            update_payload["title"] = extracted["title"]
        if extracted.get("summary") is not None:
            update_payload["summary"] = extracted["summary"]
        if extracted.get("document_type") is not None and not (existing.get("document_type") or "").strip():
            update_payload["document_type"] = extracted["document_type"]
        if extracted.get("jurisdiction") is not None and not (existing.get("jurisdiction") or "").strip():
            update_payload["jurisdiction"] = extracted["jurisdiction"]
        if extracted.get("key_points") is not None:
            update_payload["key_points"] = extracted["key_points"]
        if extracted.get("legal_principles") is not None:
            update_payload["legal_principles"] = extracted["legal_principles"]
        if extracted.get("practice_areas") is not None:
            update_payload["practice_areas"] = extracted["practice_areas"]
        if extracted.get("keywords") is not None:
            update_payload["keywords"] = extracted["keywords"]
        if extracted.get("case_name") is not None:
            update_payload["case_name"] = extracted["case_name"]
        if extracted.get("case_citation") is not None:
            update_payload["case_citation"] = extracted["case_citation"]
        if extracted.get("court_name") is not None:
            update_payload["court_name"] = extracted["court_name"]
        if extracted.get("decision_date") is not None:
            update_payload["decision_date"] = extracted["decision_date"]
        if extracted.get("statute_name") is not None:
            update_payload["statute_name"] = extracted["statute_name"]
        if extracted.get("statute_number") is not None:
            update_payload["statute_number"] = extracted["statute_number"]
        if extracted.get("enactment_date") is not None:
            update_payload["enactment_date"] = extracted["enactment_date"]
        if extracted.get("effective_date") is not None:
            update_payload["effective_date"] = extracted["effective_date"]
        if ai_embedding is not None:
            update_payload["ai_embedding"] = ai_embedding

        supabase.table("legal_knowledge_base").update(update_payload).eq("id", entry_id).execute()

        supabase.table("legal_kb_processing_jobs").update({
            "status": "completed",
            "processed_at": datetime.now(tz=timezone.utc).isoformat(),
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", job_id).execute()

        logger.info("Completed job %s entry %s", job_id, entry_id)
    except Exception as e:
        err_msg = str(e)
        logger.exception("Job %s failed: %s", job_id, err_msg)
        supabase.table("legal_kb_processing_jobs").update({
            "status": "failed",
            "last_error": err_msg[:5000],
            "processed_at": datetime.now(tz=timezone.utc).isoformat(),
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
        supabase.table("legal_knowledge_base").update({
            "processing_status": "failed",
        }).eq("id", entry_id).execute()
    finally:
        Path(file_path).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Legal KB processor worker (full Docling + PageIndex pipeline)")
    parser.add_argument("--once", action="store_true", help="Process one job and exit")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds (default 60)")
    args = parser.parse_args()

    supabase = get_supabase()

    if args.once:
        job, entry_id = poll_one_job(supabase)
        if job and entry_id:
            process_job(supabase, job, entry_id)
        else:
            logger.info("No queued jobs")
        return

    while True:
        job, entry_id = poll_one_job(supabase)
        if job and entry_id:
            process_job(supabase, job, entry_id)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
