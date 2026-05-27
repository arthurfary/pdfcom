"""
Image comparator stub.

Future implementation:
- Rasterise pages with pdf2image / pymupdf
- Compare with Pillow (pixel diff) or imagehash (perceptual hash)
- Fill location_a/location_b with tight bounding boxes for GUI overlays
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.base_comparator import BaseComparator
from models.results import ComparatorResult


class ImageComparator(BaseComparator):
    comparator_id = "image"

    def compare(self, pdf_a: str, pdf_b: str) -> ComparatorResult:
        raise NotImplementedError(
            "ImageComparator not yet implemented. "
            "Install pdf2image + Pillow and fill in this method."
        )
