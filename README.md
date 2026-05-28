# PDF Comparator

Modular PDF comparison tool. Compares two PDFs across multiple dimensions and outputs a structured JSON report with **exact bounding-box coordinates** for every diff — ready for GUI highlight overlays.

## Structure

```
pdf_comparator/
├── main.py                      ← entry point: python main.py a.pdf b.pdf
├── requirements.txt
│
├── core/
│   ├── base_comparator.py       ← abstract interface all comparators implement
│   └── engine.py                ← registers comparators, runs them, builds report
│
├── models/
│   └── results.py               ← Diff, Location, ComparatorResult, ComparisonReport
│
├── comparators/
│   ├── text_comparator.py       ← ✅ pdfminer.six – per-block text + position diff
│   ├── image_comparator.py      ← 🔲 stub
│   └── ada_comparator.py        ← 🔲 stub
│
└── tests/
    └── test_core.py
```

## Usage

```bash
pip install -r requirements.txt

python main.py doc_a.pdf doc_b.pdf
python main.py doc_a.pdf doc_b.pdf --out report.json
python main.py doc_a.pdf doc_b.pdf --comparators text
```

## How text placement works

pdfminer.six parses PDF content streams and returns `LTTextBox` objects, each
with exact `(x0, y0, x1, y1)` coordinates in PDF user-space (origin = bottom-left,
units = points).

The comparator:
1. Extracts all `LTTextBox` blocks per page from both PDFs.
2. Matches corresponding blocks by spatial position (10-pt grid bucket).
3. Diffs matched text with `SequenceMatcher`; unmatched blocks become ADDED/REMOVED.
4. Stores raw `bbox_a` / `bbox_b` tuples in `payload` and normalised (0–1) coords
   in `location_a` / `location_b` — both are available for rendering.

## Output

```json
{
  "pdf_a": "doc_a.pdf",
  "pdf_b": "doc_b.pdf",
  "overall_similarity": 0.87,
  "comparators": [
    {
      "id": "text",
      "similarity": 0.87,
      "diffs": [
        {
          "type": "changed",
          "location_a": { "page": 0, "x0": 0.05, "y0": 0.10, "x1": 0.90, "y1": 0.15 },
          "location_b": { "page": 0, "x0": 0.05, "y0": 0.10, "x1": 0.90, "y1": 0.15 },
          "description": "Page 1 | block @(1,1): changed (similarity 72.00%)",
          "payload": {
            "text_a": "Original paragraph text.",
            "text_b": "Modified paragraph text.",
            "ratio": 0.72,
            "bbox_a": [30.0, 80.0, 540.0, 120.0],
            "bbox_b": [30.0, 80.0, 540.0, 120.0]
          }
        }
      ],
      "meta": { "pages_a": 3, "pages_b": 3 }
    }
  ]
}
```

## Adding a New Comparator

```python
# comparators/my_comparator.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.base_comparator import BaseComparator
from models.results import ComparatorResult, Diff, DiffType, Location

class MyComparator(BaseComparator):
    comparator_id = "my_check"

    def compare(self, pdf_a: str, pdf_b: str) -> ComparatorResult:
        diffs = []
        # populate diffs with Location objects for GUI overlays
        return ComparatorResult(
            comparator_id=self.comparator_id,
            similarity=1.0,
            diffs=diffs,
        )
```

Then in `main.py`: `engine.register(MyComparator())`

## Running Tests

```bash
pip install pytest pdfminer.six
pytest tests/
```
