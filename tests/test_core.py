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
from models.results import ComparatorResult, ComparisonReport
from comparators.text_comparator import TextComparator


class _DummyComparator(BaseComparator):
    comparator_id = "dummy"

    def compare(self, pdf_a, pdf_b):
        return ComparatorResult(comparator_id="dummy", similarity=0.5)


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


class TestTextComparator:
    def _run(self, pages_a, pages_b):
        comp = TextComparator()
        with patch.object(TextComparator, "_extract_pages", side_effect=[pages_a, pages_b]):
            return comp.compare("a.pdf", "b.pdf")

    def test_identical(self):
        result = self._run(["hello world"], ["hello world"])
        assert result.similarity == 1.0
        assert result.diffs == []

    def test_different(self):
        result = self._run(["aaa"], ["bbb"])
        assert result.similarity < 1.0
        assert len(result.diffs) == 1

    def test_page_count_mismatch(self):
        result = self._run(["page1", "page2"], ["page1"])
        assert result.similarity < 1.0


class TestReport:
    def test_to_dict(self):
        report = ComparisonReport(pdf_a="a.pdf", pdf_b="b.pdf", overall_similarity=0.75)
        d = report.to_dict()
        assert d["overall_similarity"] == 0.75
        assert "comparators" in d
