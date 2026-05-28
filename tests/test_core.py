"""
Tests – run from the project root:  pytest tests/
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch

from core.engine import ComparisonEngine
from core.base_comparator import BaseComparator
from models.results import ComparatorResult, ComparisonReport, DiffType
from comparators.text_comparator import TextComparator, TextBlock, _blocks_to_snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _DummyComparator(BaseComparator):
    comparator_id = "dummy"

    def compare(self, pdf_a, pdf_b):
        return ComparatorResult(comparator_id="dummy", similarity=0.5)


def _block(text, x0=0, y0=0, x1=100, y1=20, pw=600, ph=800):
    return TextBlock(text=text, x0=x0, y0=y0, x1=x1, y1=y1,
                     page_width=pw, page_height=ph)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TestEngine:
    def test_register_and_run(self, tmp_path):
        a = tmp_path / "a.pdf"; a.write_bytes(b"%PDF-1.4")
        b = tmp_path / "b.pdf"; b.write_bytes(b"%PDF-1.4")
        engine = ComparisonEngine()
        engine.register(_DummyComparator())
        report = engine.run(str(a), str(b))
        assert report.overall_similarity == 0.5
        assert len(report.results) == 1

    def test_missing_file_raises(self, tmp_path):
        a = tmp_path / "a.pdf"; a.write_bytes(b"%PDF-1.4")
        engine = ComparisonEngine()
        engine.register(_DummyComparator())
        with pytest.raises(FileNotFoundError):
            engine.run(str(a), "no_such.pdf")

    def test_no_comparators_raises(self, tmp_path):
        a = tmp_path / "a.pdf"; a.write_bytes(b"%PDF-1.4")
        b = tmp_path / "b.pdf"; b.write_bytes(b"%PDF-1.4")
        engine = ComparisonEngine()
        with pytest.raises(RuntimeError):
            engine.run(str(a), str(b))


# ---------------------------------------------------------------------------
# TextBlock / Location normalisation
# ---------------------------------------------------------------------------

class TestTextBlock:
    def test_location_normalised(self):
        b = _block("hello", x0=60, y0=80, x1=120, y1=100, pw=600, ph=800)
        loc = b.location(page_index=2)
        assert loc.page == 2
        assert abs(loc.x0 - 0.1) < 1e-6
        assert abs(loc.y0 - 0.1) < 1e-6
        assert abs(loc.x1 - 0.2) < 1e-6
        assert abs(loc.y1 - 0.125) < 1e-6


# ---------------------------------------------------------------------------
# TextComparator (mocked extraction)
# ---------------------------------------------------------------------------

class TestTextComparator:
    def _run(self, pages_a, pages_b):
        comp = TextComparator()
        with patch("comparators.text_comparator._extract_blocks",
                   side_effect=[pages_a, pages_b]):
            return comp.compare("a.pdf", "b.pdf")

    def test_identical(self):
        b = _block("hello world", x0=10, y0=10)
        result = self._run([[b]], [[b]])
        assert result.similarity == 1.0
        assert result.diffs == []

    def test_changed_block(self):
        ba = _block("original text", x0=10, y0=10)
        bb = _block("modified text", x0=10, y0=10)
        result = self._run([[ba]], [[bb]])
        assert result.similarity < 1.0
        assert len(result.diffs) == 1
        assert result.diffs[0].diff_type == DiffType.CHANGED

    def test_added_block(self):
        bb = _block("new text", x0=10, y0=10)
        result = self._run([[]], [[bb]])
        assert result.diffs[0].diff_type == DiffType.ADDED
        assert result.diffs[0].location_a is None

    def test_removed_block(self):
        ba = _block("old text", x0=10, y0=10)
        result = self._run([[ba]], [[]])
        assert result.diffs[0].diff_type == DiffType.REMOVED
        assert result.diffs[0].location_b is None

    def test_payload_contains_bboxes(self):
        ba = _block("before", x0=10, y0=10, x1=100, y1=30)
        bb = _block("after",  x0=10, y0=10, x1=100, y1=30)
        result = self._run([[ba]], [[bb]])
        p = result.diffs[0].payload
        assert p["bbox_a"] == (10, 10, 100, 30)
        assert p["bbox_b"] == (10, 10, 100, 30)
        assert "ratio" in p

    def test_page_count_mismatch(self):
        ba = _block("page1", x0=10, y0=10)
        result = self._run([[ba], [ba]], [[ba]])
        assert result.similarity < 1.0


# ---------------------------------------------------------------------------
# Report serialisation
# ---------------------------------------------------------------------------

class TestReport:
    def test_to_dict(self):
        report = ComparisonReport(pdf_a="a.pdf", pdf_b="b.pdf", overall_similarity=0.75)
        d = report.to_dict()
        assert d["overall_similarity"] == 0.75
        assert "comparators" in d
