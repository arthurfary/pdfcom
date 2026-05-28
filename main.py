"""
PDF Comparator – main entry point.

Usage
-----
python main.py doc_a.pdf doc_b.pdf
python main.py doc_a.pdf doc_b.pdf --comparators text image
python main.py doc_a.pdf doc_b.pdf --out report.json
python main.py doc_a.pdf doc_b.pdf --save-masks --mask-dir ./masks
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import json
import logging

from core.engine import ComparisonEngine
from comparators.text_comparator import TextComparator
from comparators.image_comparator import ImageComparator
# from comparators.ada_comparator import ADAComparator  # uncomment when ready


def build_engine(args) -> ComparisonEngine:
    engine = ComparisonEngine()
    engine.register(TextComparator())
    engine.register(ImageComparator(
        dpi=args.dpi,
        save_masks=args.save_masks,
        mask_dir=args.mask_dir,
    ))
    # engine.register(ADAComparator())
    return engine


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Compare two PDF files and output a similarity report."
    )
    parser.add_argument("pdf_a", help="Path to reference PDF")
    parser.add_argument("pdf_b", help="Path to PDF being compared")
    parser.add_argument(
        "--comparators", nargs="+", metavar="ID", default=None,
        help="Comparator IDs to run (default: all). E.g. --comparators text image",
    )
    parser.add_argument("--out", metavar="FILE", default=None,
        help="Write JSON report to FILE instead of stdout")
    parser.add_argument("--dpi", type=int, default=150,
        help="DPI for image rasterisation (default: 150)")
    parser.add_argument("--save-masks", action="store_true",
        help="Save diff mask PNGs alongside the report")
    parser.add_argument("--mask-dir", metavar="DIR", default=None,
        help="Directory to write mask images (default: system temp dir)")
    args = parser.parse_args()

    engine = build_engine(args)

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
