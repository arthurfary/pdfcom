# PDF Comparator

Modular PDF comparison tool. Compares two PDFs across multiple dimensions (text, image, ADA) and outputs a structured JSON report with exact diff locations — ready for GUI overlay rendering.

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
│   ├── text_comparator.py       ← ✅ implemented (pdfplumber + SequenceMatcher)
│   ├── image_comparator.py      ← 🔲 stub
│   └── ada_comparator.py        ← 🔲 stub
│
└── tests/
    └── test_core.py
```

## Usage

```bash
pip install -r requirements.txt

# print JSON report to stdout
python main.py doc_a.pdf doc_b.pdf

# save to file
python main.py doc_a.pdf doc_b.pdf --out report.json

# run specific comparators only
python main.py doc_a.pdf doc_b.pdf --comparators text
```

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
          "location_a": { "page": 0, "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0 },
          "location_b": { "page": 0, "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0 },
          "description": "Page 1: text similarity 87.00%",
          "payload": { "text_a": "...", "text_b": "...", "ratio": 0.87 }
        }
      ],
      "meta": { "pages_a": 3, "pages_b": 3 }
    }
  ]
}
```

Each `Diff` carries `location_a` / `location_b` with page index and normalised bounding-box coordinates (0–1) so a GUI can draw highlights directly on the rendered PDF.

## Adding a New Comparator

1. Create `comparators/my_comparator.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.base_comparator import BaseComparator
from models.results import ComparatorResult, Diff, DiffType, Location

class MyComparator(BaseComparator):
    comparator_id = "my_check"

    def compare(self, pdf_a: str, pdf_b: str) -> ComparatorResult:
        diffs = []
        # ... your logic ...
        return ComparatorResult(comparator_id=self.comparator_id, similarity=1.0, diffs=diffs)
```

2. Register it in `main.py`:

```python
from comparators.my_comparator import MyComparator
engine.register(MyComparator())
```

## Running Tests

```bash
pip install pytest
pytest tests/
```
