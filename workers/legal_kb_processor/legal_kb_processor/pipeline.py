"""
Docling + PageIndex pipeline: convert document to markdown/JSON, then build PageIndex tree.
Docling is pip-installed; PageIndex is used from local repo at PAGEINDEX_ROOT.
"""
import asyncio
import sys
import tempfile
from pathlib import Path

from docling.document_converter import DocumentConverter

from .config import PAGEINDEX_ROOT


def _add_pageindex_path() -> None:
    """Add local PageIndex repo to path so we can import pageindex."""
    if PAGEINDEX_ROOT.exists() and str(PAGEINDEX_ROOT) not in sys.path:
        sys.path.insert(0, str(PAGEINDEX_ROOT))


def run_docling(file_path: str) -> tuple[str, dict]:
    """
    Run Docling on a file; return (markdown_text, structured_dict).
    Requires: pip install docling
    """
    converter = DocumentConverter()
    result = converter.convert(file_path)
    doc = result.document
    markdown_text = doc.export_to_markdown()
    structured = doc.export_to_dict()
    return markdown_text, structured


def run_pageindex_from_markdown(markdown_text: str, add_summary: bool = False) -> dict:
    """
    Build PageIndex tree from markdown string.
    Uses pageindex.page_index_md.md_to_tree (async); runs in event loop.
    """
    _add_pageindex_path()
    from pageindex.page_index_md import md_to_tree

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(markdown_text)
        md_path = f.name

    try:
        tree_result = asyncio.run(
            md_to_tree(
                md_path,
                if_thinning=False,
                if_add_node_summary="yes" if add_summary else "no",
                if_add_doc_description="no",
                if_add_node_text="no",
                if_add_node_id="yes",
            )
        )
        return tree_result
    finally:
        Path(md_path).unlink(missing_ok=True)


def tree_depth_and_count(tree: dict) -> tuple[int, int]:
    """Compute depth and node count of PageIndex tree (structure list)."""
    structure = tree.get("structure", tree) if isinstance(tree, dict) else tree
    if not structure:
        return 0, 0

    def visit(nodes: list, depth: int) -> tuple[int, int]:
        if not nodes:
            return depth, 0
        count = 0
        max_d = depth
        for node in nodes:
            count += 1
            children = node.get("nodes") or []
            sub_d, sub_c = visit(children, depth + 1)
            count += sub_c
            max_d = max(max_d, sub_d)
        return max_d, count

    max_depth, total = visit(structure if isinstance(structure, list) else [structure], 1)
    return max_depth, total
