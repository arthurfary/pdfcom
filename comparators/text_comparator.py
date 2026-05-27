"""
Text comparator – extracts text per page and scores similarity via SequenceMatcher.

Diff payload keys:
  text_a  – original text block
  text_b  – new text block
  ratio   – SequenceMatcher ratio for that page
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import difflib
import logging

import pdfplumber

from core.base_comparator import BaseComparator
from models.results import ComparatorResult, Diff, DiffType, Location

logger = logging.getLogger(__name__)


class TextComparator(BaseComparator):
    comparator_id = "text"

    def compare(self, pdf_a: str, pdf_b: str) -> ComparatorResult:
        pages_a = self._extract_pages(pdf_a)
        pages_b = self._extract_pages(pdf_b)

        diffs: list[Diff] = []
        page_scores: list[float] = []
        n_pages = max(len(pages_a), len(pages_b))

        for i in range(n_pages):
            text_a = pages_a[i] if i < len(pages_a) else ""
            text_b = pages_b[i] if i < len(pages_b) else ""

            ratio = difflib.SequenceMatcher(None, text_a, text_b).ratio()
            page_scores.append(ratio)

            if ratio < 1.0:
                diff_type = (
                    DiffType.ADDED   if not text_a else
                    DiffType.REMOVED if not text_b else
                    DiffType.CHANGED
                )
                diffs.append(Diff(
                    diff_type=diff_type,
                    location_a=Location(page=i) if text_a else None,
                    location_b=Location(page=i) if text_b else None,
                    description=f"Page {i + 1}: text similarity {ratio:.2%}",
                    payload={"text_a": text_a, "text_b": text_b, "ratio": ratio},
                ))

        similarity = sum(page_scores) / len(page_scores) if page_scores else 1.0

        return ComparatorResult(
            comparator_id=self.comparator_id,
            similarity=similarity,
            diffs=diffs,
            meta={"pages_a": len(pages_a), "pages_b": len(pages_b)},
        )

    @staticmethod
    def _extract_pages(path: str) -> list[str]:
        pages: list[str] = []
        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
        except Exception:
            logger.exception("Failed to extract text from %s", path)
        return pages
