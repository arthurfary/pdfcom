"""
ADA / Accessibility comparator stub.

Future implementation:
- Check tagged PDF structure (MarkInfo, StructTreeRoot)
- Verify alt-text on images
- Check reading order, language metadata, bookmarks
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.base_comparator import BaseComparator
from models.results import ComparatorResult


class ADAComparator(BaseComparator):
    comparator_id = "ada"

    def compare(self, pdf_a: str, pdf_b: str) -> ComparatorResult:
        raise NotImplementedError("ADAComparator not yet implemented.")
