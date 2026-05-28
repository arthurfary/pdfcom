"""
Orchestrates comparators and builds the final ComparisonReport.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
from pathlib import Path

from core.base_comparator import BaseComparator
from models.results import ComparisonReport

logger = logging.getLogger(__name__)


class ComparisonEngine:
    def __init__(self) -> None:
        self._comparators: dict[str, BaseComparator] = {}

    def register(self, comparator: BaseComparator) -> None:
        cid = comparator.comparator_id
        if not cid:
            raise ValueError(f"{comparator.__class__.__name__} must define comparator_id")
        self._comparators[cid] = comparator
        logger.debug("Registered comparator: %s", cid)

    def unregister(self, comparator_id: str) -> None:
        self._comparators.pop(comparator_id, None)

    def run(
        self,
        pdf_a: str,
        pdf_b: str,
        comparator_ids: list[str] | None = None,
    ) -> ComparisonReport:
        self._validate_files(pdf_a, pdf_b)

        targets = (
            {k: v for k, v in self._comparators.items() if k in comparator_ids}
            if comparator_ids
            else self._comparators
        )
        if not targets:
            raise RuntimeError("No comparators available to run.")

        report = ComparisonReport(pdf_a=pdf_a, pdf_b=pdf_b)

        for cid, comparator in targets.items():
            logger.info("Running comparator: %s", cid)
            try:
                result = comparator.compare(pdf_a, pdf_b)
                report.results.append(result)
            except Exception:
                logger.exception("Comparator '%s' failed.", cid)

        if report.results:
            report.overall_similarity = sum(r.similarity for r in report.results) / len(
                report.results
            )

        return report

    @staticmethod
    def _validate_files(*paths: str) -> None:
        for p in paths:
            path = Path(p)
            if not path.exists():
                raise FileNotFoundError(f"PDF not found: {p}")
            if path.suffix.lower() != ".pdf":
                raise ValueError(f"Not a PDF file: {p}")
