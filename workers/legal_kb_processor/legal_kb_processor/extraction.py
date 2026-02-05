"""
LLM-based legal metadata extraction from Docling markdown.
Fills title, summary, key_points, legal_principles, case/statute fields, practice_areas, keywords.
"""
import json
import logging
import re
from typing import Any

from openai import OpenAI

from .config import LLM_MAX_RETRIES, LLM_MODEL, MAX_MARKDOWN_FOR_EXTRACTION, OPENAI_API_KEY

logger = logging.getLogger(__name__)

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short document title"},
        "summary": {"type": "string", "description": "Concise summary (2-4 sentences)"},
        "document_type": {"type": "string", "enum": ["case_law", "statute", "regulation", "legal_article", "template"]},
        "jurisdiction": {"type": "string", "description": "e.g. Kenya, U.S., UK"},
        "case_name": {"type": "string"},
        "case_citation": {"type": "string"},
        "court_name": {"type": "string"},
        "decision_date": {"type": "string", "description": "YYYY-MM-DD or null"},
        "statute_name": {"type": "string"},
        "statute_number": {"type": "string"},
        "enactment_date": {"type": "string"},
        "effective_date": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "legal_principles": {"type": "array", "items": {"type": "string"}},
        "practice_areas": {"type": "array", "items": {"type": "string"}},
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


def _truncate_markdown(markdown: str, max_chars: int) -> str:
    if len(markdown) <= max_chars:
        return markdown
    return markdown[:max_chars] + "\n\n[... truncated for context ...]"


def extract_legal_metadata(
    markdown: str,
    existing: dict[str, Any] | None = None,
    docling_sections_hint: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Use LLM to extract legal metadata from markdown.
    Only sets fields that are empty in existing (so user-provided values are preserved).
    """
    existing = existing or {}
    hint = ""
    if docling_sections_hint:
        try:
            titles = [s.get("title") or s.get("heading") for s in docling_sections_hint[:30] if isinstance(s, dict)]
            hint = "Document section headings (from structure): " + ", ".join(filter(None, titles))
        except Exception:
            pass

    text = _truncate_markdown(markdown, MAX_MARKDOWN_FOR_EXTRACTION)

    prompt = f"""Extract legal metadata from the following document text. Return valid JSON only.

{hint}

Document text:
---
{text}
---

Rules:
- Infer document_type (case_law, statute, regulation, legal_article, template) from content.
- Infer jurisdiction (country or region) from content.
- For case law: extract case_name, case_citation, court_name, decision_date (YYYY-MM-DD).
- For statutes: extract statute_name, statute_number, enactment_date, effective_date.
- key_points: 3-7 bullet points.
- legal_principles: 1-5 principles or holdings.
- practice_areas and keywords: relevant legal areas and search terms.
- Use null for missing fields. Use empty array [] for missing lists.
- Return only a single JSON object, no markdown fences."""

    client = OpenAI(api_key=OPENAI_API_KEY)
    last_error = None
    for attempt in range(LLM_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = (response.choices[0].message.content or "").strip()
            # Strip markdown code block if present
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```\s*$", "", raw)
            data = json.loads(raw)

            # Merge: only set keys that are empty in existing
            out = {}
            for key in EXTRACTION_SCHEMA.get("properties", {}):
                if key not in data:
                    continue
                val = data[key]
                existing_val = existing.get(key)
                if existing_val is not None and existing_val != "" and (not isinstance(existing_val, list) or len(existing_val) > 0):
                    continue
                if val is None or val == "" or (isinstance(val, list) and len(val) == 0):
                    continue
                out[key] = val
            return out
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning("LLM extraction JSON parse attempt %s: %s", attempt + 1, e)
        except Exception as e:
            last_error = e
            logger.warning("LLM extraction attempt %s: %s", attempt + 1, e)

    raise RuntimeError(f"Legal metadata extraction failed after {LLM_MAX_RETRIES} attempts: {last_error}")
