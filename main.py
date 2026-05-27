"""
PDF Comparator – main entry point.

Usage
-----
python main.py doc_a.pdf doc_b.pdf
python main.py doc_a.pdf doc_b.pdf --comparators text
python main.py doc_a.pdf doc_b.pdf --out report.json
"""

import sys
import os

# Make sure sibling folders are importable without installation
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import json
import logging

from core.engine import ComparisonEngine
from comparators.text_comparator import TextComparator
# from comparators.image_comparator import ImageComparator  # uncomment when ready
# from comparators.ada_comparator import ADAComparator      # uncomment when ready


def build_engine() -> ComparisonEngine:
    engine = ComparisonEngine()
    engine.register(TextComparator())
    # engine.register(ImageComparator())
    # engine.register(ADAComparator())
    return engine


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Compare two PDF files and output a similarity report.")
    parser.add_argument("pdf_a", help="Path to reference PDF")
    parser.add_argument("pdf_b", help="Path to PDF being compared")
    parser.add_argument(
        "--comparators",
        nargs="+",
        metavar="ID",
        default=None,
        help="Comparator IDs to run (default: all). E.g. --comparators text",
    )
    parser.add_argument(
        "--out",
        metavar="FILE",
        default=None,
        help="Write JSON report to FILE instead of stdout",
    )
    args = parser.parse_args()

    engine = build_engine()

    try:
        report = engine.run(args.pdf_a, args.pdf_b, comparator_ids=args.comparators)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"Report written to {args.out}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
