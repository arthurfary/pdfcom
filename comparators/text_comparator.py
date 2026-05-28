"""
Text comparator – uses pdfminer.six to extract positioned text blocks,
then matches them with a two-phase strategy designed to handle both
minor layout shifts and genuine content changes.

Matching strategy (per page)
-----------------------------
Phase 1 – Exact text match.
  For each unique text that appears in both A and B, pair the occurrences
  by proximity (closest centre-point first).  This handles documents that
  are content-identical but have been re-flowed or re-exported with small
  coordinate shifts.

Phase 2 – Spatial fallback for unmatched blocks.
  Any blocks that had no exact-text match are paired by nearest-neighbour
  within `match_radius` points.  This catches blocks whose text genuinely
  changed but whose position is stable (e.g. a cell value that was edited).

Rationale
---------
Pure spatial matching fails when the whole page shifts (e.g. a consistent
14pt vertical offset), because nearby rows get mis-paired.  Pure text
matching fails when content changes but the block stays in place.  The
combination handles both cases correctly.

Diff payload keys
-----------------
  text_a   – text from PDF-A block (or "")
  text_b   – text from PDF-B block (or "")
  ratio    – SequenceMatcher similarity (1.0 for identical blocks)
  bbox_a   – raw (x0,y0,x1,y1) in PDF points, or None
  bbox_b   – raw (x0,y0,x1,y1) in PDF points, or None
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import difflib
import logging
import math
from collections import defaultdict
from dataclasses import dataclass

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextBox

from core.base_comparator import BaseComparator
from models.results import ComparatorResult, Diff, DiffType, Location

logger = logging.getLogger(__name__)

DEFAULT_MATCH_RADIUS = 40.0  # PDF points; ~0.56 inch


@dataclass
class TextBlock:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    def distance_to(self, other: "TextBlock") -> float:
        return math.sqrt((self.cx - other.cx) ** 2 + (self.cy - other.cy) ** 2)

    def location(self, page_index: int) -> Location:
        w = self.page_width or 1
        h = self.page_height or 1
        return Location(
            page=page_index,
            x0=self.x0 / w,
            y0=self.y0 / h,
            x1=self.x1 / w,
            y1=self.y1 / h,
        )


def _extract_blocks(path: str) -> list[list[TextBlock]]:
    pages: list[list[TextBlock]] = []
    try:
        for page_layout in extract_pages(path, laparams=LAParams()):
            blocks: list[TextBlock] = []
            pw, ph = page_layout.width, page_layout.height
            for el in page_layout:
                if isinstance(el, LTTextBox):
                    blocks.append(
                        TextBlock(
                            text=el.get_text().strip(),
                            x0=el.x0,
                            y0=el.y0,
                            x1=el.x1,
                            y1=el.y1,
                            page_width=pw,
                            page_height=ph,
                        )
                    )
            pages.append(blocks)
    except Exception:
        logger.exception("Failed to extract text blocks from %s", path)
    return pages


def _match_blocks(
    blocks_a: list[TextBlock],
    blocks_b: list[TextBlock],
    match_radius: float,
) -> tuple[list[tuple[TextBlock, TextBlock]], list[TextBlock], list[TextBlock]]:
    """
    Two-phase matching.  Returns (matched_pairs, only_in_a, only_in_b).
    """
    unmatched_a = list(range(len(blocks_a)))
    unmatched_b = list(range(len(blocks_b)))
    matched: list[tuple[TextBlock, TextBlock]] = []

    # ── Phase 1: exact text match, paired by proximity ──────────────────
    by_text_b: dict[str, list[int]] = defaultdict(list)
    for j in unmatched_b:
        by_text_b[blocks_b[j].text].append(j)

    still_unmatched_a: list[int] = []
    consumed_b: set[int] = set()

    for i in unmatched_a:
        ba = blocks_a[i]
        candidates = [j for j in by_text_b.get(ba.text, []) if j not in consumed_b]
        if not candidates:
            still_unmatched_a.append(i)
            continue
        # Pick the closest candidate
        j = min(candidates, key=lambda j: ba.distance_to(blocks_b[j]))
        matched.append((ba, blocks_b[j]))
        consumed_b.add(j)

    remaining_b = [j for j in unmatched_b if j not in consumed_b]

    # ── Phase 2: spatial fallback for remaining blocks ───────────────────
    candidates_spatial: list[tuple[float, int, int]] = []
    for i in still_unmatched_a:
        for j in remaining_b:
            d = blocks_a[i].distance_to(blocks_b[j])
            if d <= match_radius:
                candidates_spatial.append((d, i, j))
    candidates_spatial.sort()

    used_a: set[int] = set()
    used_b: set[int] = set()
    for d, i, j in candidates_spatial:
        if i in used_a or j in used_b:
            continue
        matched.append((blocks_a[i], blocks_b[j]))
        used_a.add(i)
        used_b.add(j)

    only_a = [blocks_a[i] for i in still_unmatched_a if i not in used_a]
    only_b = [blocks_b[j] for j in remaining_b if j not in used_b]
    return matched, only_a, only_b


class TextComparator(BaseComparator):
    comparator_id = "text"

    def __init__(self, match_radius: float = DEFAULT_MATCH_RADIUS) -> None:
        self.match_radius = match_radius

    def compare(self, pdf_a: str, pdf_b: str) -> ComparatorResult:
        pages_a = _extract_blocks(pdf_a)
        pages_b = _extract_blocks(pdf_b)

        diffs: list[Diff] = []
        page_scores: list[float] = []

        for i in range(max(len(pages_a), len(pages_b))):
            blocks_a = pages_a[i] if i < len(pages_a) else []
            blocks_b = pages_b[i] if i < len(pages_b) else []
            page_diffs, score = self._compare_page(i, blocks_a, blocks_b)
            diffs.extend(page_diffs)
            page_scores.append(score)

        similarity = sum(page_scores) / len(page_scores) if page_scores else 1.0
        return ComparatorResult(
            comparator_id=self.comparator_id,
            similarity=similarity,
            diffs=diffs,
            meta={"pages_a": len(pages_a), "pages_b": len(pages_b)},
        )

    def _compare_page(
        self,
        page_index: int,
        blocks_a: list[TextBlock],
        blocks_b: list[TextBlock],
    ) -> tuple[list[Diff], float]:
        matched, only_a, only_b = _match_blocks(blocks_a, blocks_b, self.match_radius)

        diffs: list[Diff] = []
        scores: list[float] = []

        for ba, bb in matched:
            ratio = difflib.SequenceMatcher(None, ba.text, bb.text).ratio()
            scores.append(ratio)
            if ratio < 1.0:
                diffs.append(
                    Diff(
                        diff_type=DiffType.CHANGED,
                        location_a=ba.location(page_index),
                        location_b=bb.location(page_index),
                        description=f"Page {page_index + 1}: text changed (similarity {ratio:.2%})",
                        payload={
                            "text_a": ba.text,
                            "text_b": bb.text,
                            "ratio": ratio,
                            "bbox_a": (ba.x0, ba.y0, ba.x1, ba.y1),
                            "bbox_b": (bb.x0, bb.y0, bb.x1, bb.y1),
                        },
                    )
                )

        for ba in only_a:
            scores.append(0.0)
            diffs.append(
                Diff(
                    diff_type=DiffType.REMOVED,
                    location_a=ba.location(page_index),
                    location_b=None,
                    description=f"Page {page_index + 1}: block removed — {ba.text[:60]!r}",
                    payload={
                        "text_a": ba.text,
                        "text_b": "",
                        "ratio": 0.0,
                        "bbox_a": (ba.x0, ba.y0, ba.x1, ba.y1),
                        "bbox_b": None,
                    },
                )
            )

        for bb in only_b:
            scores.append(0.0)
            diffs.append(
                Diff(
                    diff_type=DiffType.ADDED,
                    location_a=None,
                    location_b=bb.location(page_index),
                    description=f"Page {page_index + 1}: block added — {bb.text[:60]!r}",
                    payload={
                        "text_a": "",
                        "text_b": bb.text,
                        "ratio": 0.0,
                        "bbox_a": None,
                        "bbox_b": (bb.x0, bb.y0, bb.x1, bb.y1),
                    },
                )
            )

        page_score = sum(scores) / len(scores) if scores else 1.0
        return diffs, page_score
