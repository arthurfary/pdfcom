"""
Data models for comparison results.
Each Diff carries location data so a GUI can render exact change overlays.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DiffType(str, Enum):
    ADDED   = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    EQUAL   = "equal"


@dataclass
class Location:
    """Normalised (0-1) bounding box on a PDF page."""
    page: int
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 1.0
    y1: float = 1.0


@dataclass
class Diff:
    """One atomic difference between the two documents."""
    diff_type: DiffType
    location_a: Location | None       # position in PDF-A (None = not present)
    location_b: Location | None       # position in PDF-B (None = not present)
    description: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparatorResult:
    """Result from a single comparator."""
    comparator_id: str
    similarity: float                 # 0.0 – 1.0
    diffs: list[Diff] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonReport:
    """Aggregated report across all comparators."""
    pdf_a: str
    pdf_b: str
    overall_similarity: float = 0.0
    results: list[ComparatorResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pdf_a": self.pdf_a,
            "pdf_b": self.pdf_b,
            "overall_similarity": round(self.overall_similarity, 4),
            "comparators": [
                {
                    "id": r.comparator_id,
                    "similarity": round(r.similarity, 4),
                    "diffs": [
                        {
                            "type": d.diff_type.value,
                            "location_a": vars(d.location_a) if d.location_a else None,
                            "location_b": vars(d.location_b) if d.location_b else None,
                            "description": d.description,
                            "payload": d.payload,
                        }
                        for d in r.diffs
                    ],
                    "meta": r.meta,
                }
                for r in self.results
            ],
        }
