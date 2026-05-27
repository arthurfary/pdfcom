"""
Abstract base class every comparator must implement.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from abc import ABC, abstractmethod
from models.results import ComparatorResult


class BaseComparator(ABC):
    comparator_id: str = ""

    @abstractmethod
    def compare(self, pdf_a: str, pdf_b: str) -> ComparatorResult:
        """Compare two PDFs and return a ComparatorResult."""
