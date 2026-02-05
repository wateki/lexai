"""
Legal citation parsing using eyecite (pip-installed).
Splits case citations and statute/law citations for cited_cases and cited_statutes.
"""
import logging

from eyecite import get_citations
from eyecite.models import FullCaseCitation, FullLawCitation

logger = logging.getLogger(__name__)


def parse_citations(plain_text: str) -> tuple[list[str], list[str]]:
    """
    Parse legal citations from text using eyecite.
    Returns (cited_cases, cited_statutes) as lists of citation strings.
    Requires: pip install eyecite
    """

    try:
        citations = get_citations(plain_text=plain_text)
    except Exception as e:
        logger.warning("eyecite get_citations failed: %s", e)
        return [], []

    cited_cases: list[str] = []
    cited_statutes: list[str] = []
    seen_case: set[str] = set()
    seen_statute: set[str] = set()

    for c in citations:
        try:
            cite_str = c.corrected_citation() or c.matched_text() or str(getattr(c, "token", c))
            if not cite_str or not cite_str.strip():
                continue
            if isinstance(c, FullCaseCitation):
                if cite_str not in seen_case:
                    seen_case.add(cite_str)
                    cited_cases.append(cite_str)
            elif isinstance(c, FullLawCitation):
                if cite_str not in seen_statute:
                    seen_statute.add(cite_str)
                    cited_statutes.append(cite_str)
        except Exception as e:
            logger.debug("Skipping citation: %s", e)

    return cited_cases, cited_statutes
