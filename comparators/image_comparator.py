"""
Image comparator – rasterises each page pair and produces three masks:

  mask_diff     Black/white binary: white = any pixel that changed.
                Union of added + removed. Same as before, useful for
                measuring the total changed area.

  mask_added    Black/white binary: white = pixels B has that A doesn't
                (new ink in B). Overlay this on A to see what B added.

  mask_removed  Black/white binary: white = pixels A has that B doesn't
                (ink that disappeared). Overlay this on B to see what
                was taken away.

  mask_overlay  RGBA: B's actual pixels, transparent where unchanged.
                Drop this on top of A in a GUI to see exactly what moved.

Scoring
-------
raw_diff_ratio  = (added_pixels + removed_pixels) / total_pixels

Amplification curve: diff = log(1 + raw * k) / log(1 + k),  k = 50

  raw  0.0% → diff  0%   identical
  raw  0.5% → diff  6%   near-identical (rendering noise)
  raw  3.0% → diff 23%   table alignment shift: noticeable
  raw 10  % → diff 46%   significant layout change
  raw 50  % → diff 83%   major restructure

Diff payload keys
-----------------
  raw_diff_ratio      fraction of pixels that changed (0-1)
  amplified_diff      after log curve (0-1)
  added_ratio         fraction of pixels B added
  removed_ratio       fraction of pixels B removed
  threshold           pixel threshold used
  dpi                 rasterisation DPI
  mask_diff           path to diff mask PNG     (if save_masks=True)
  mask_added          path to added mask PNG    (if save_masks=True)
  mask_removed        path to removed mask PNG  (if save_masks=True)
  mask_overlay        path to RGBA overlay PNG  (if save_masks=True)
  page_width_px       rasterised width in pixels
  page_height_px      rasterised height in pixels
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
import math
import tempfile
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageFilter
    from pdf2image import convert_from_path

    _DEPS_OK = True
except ImportError:
    _DEPS_OK = False

from core.base_comparator import BaseComparator
from models.results import ComparatorResult, Diff, DiffType, Location

logger = logging.getLogger(__name__)

DEFAULT_DPI = 300
DEFAULT_THRESHOLD = 15  # pixel intensity delta below this = noise
DEFAULT_BLUR_RADIUS = 0  # pre-diff Gaussian blur to suppress hinting jitter
AMPLIFICATION_K = 1


def _amplify(raw: float, k: float = AMPLIFICATION_K) -> float:
    if raw <= 0:
        return 0.0
    return math.log(1 + raw * k) / math.log(1 + k)


def _rasterise(path: str, dpi: int) -> list["Image.Image"]:
    return convert_from_path(path, dpi=dpi)


def _build_masks(
    img_a: "Image.Image",
    img_b: "Image.Image",
    blur_radius: float,
    threshold: int,
) -> dict:
    """
    Returns a dict with:
      added_mask    np.uint8 (H,W)  – 255 where B has new ink
      removed_mask  np.uint8 (H,W)  – 255 where A ink disappeared
      diff_mask     np.uint8 (H,W)  – 255 where anything changed (union)
      overlay_rgba  np.uint8 (H,W,4)– green=added in B, red=removed from A, transparent elsewhere
      added_ratio   float
      removed_ratio float
      raw_diff_ratio float
    """
    if img_b.size != img_a.size:
        img_b = img_b.resize(img_a.size, Image.LANCZOS)

    # Raw pixel arrays (greyscale, no blur) for directional diff
    arr_a = np.array(img_a.convert("L"))
    arr_b = np.array(img_b.convert("L"))

    # Blurred arrays for the region mask (cleaner blobs, fewer isolated dots)
    blur_a = np.array(img_a.convert("L").filter(ImageFilter.GaussianBlur(blur_radius)))
    blur_b = np.array(img_b.convert("L").filter(ImageFilter.GaussianBlur(blur_radius)))

    signed = arr_a.astype(np.int16) - arr_b.astype(np.int16)

    # Directional masks (unblurred = precise pixel positions)
    added_px = signed > threshold  # A=white, B=ink → B added this
    removed_px = signed < -threshold  # A=ink, B=white → B removed this

    # Region mask (blurred = connected blobs, better for overlay alpha)
    diff_region = np.abs(blur_a.astype(np.int16) - blur_b.astype(np.int16)) > threshold

    h, w = arr_b.shape

    added_mask = np.where(added_px, 255, 0).astype(np.uint8)
    removed_mask = np.where(removed_px, 255, 0).astype(np.uint8)
    diff_mask = np.where(diff_region, 255, 0).astype(np.uint8)

    # RGBA overlay: green = B added ink, red = B removed ink, transparent = unchanged.
    # Alpha 180/255 (~70%) keeps the underlying PDF readable through the highlight.
    overlay_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    overlay_rgba[added_px, :] = [0, 200, 0, 180]  # green: new in B
    overlay_rgba[removed_px, :] = [200, 0, 0, 180]  # red:   gone in B

    total = h * w
    return {
        "added_mask": added_mask,
        "removed_mask": removed_mask,
        "diff_mask": diff_mask,
        "overlay_rgba": overlay_rgba,
        "added_ratio": float(added_px.sum()) / total,
        "removed_ratio": float(removed_px.sum()) / total,
        "raw_diff_ratio": float(diff_region.sum()) / total,
    }


def _save_mask(arr: np.ndarray, path: str, mode: str = "L") -> None:
    Image.fromarray(arr, mode=mode).save(path)


class ImageComparator(BaseComparator):
    comparator_id = "image"

    def __init__(
        self,
        dpi: int = DEFAULT_DPI,
        threshold: int = DEFAULT_THRESHOLD,
        blur_radius: float = DEFAULT_BLUR_RADIUS,
        save_masks: bool = False,
        mask_dir: str | None = None,
    ) -> None:
        if not _DEPS_OK:
            raise ImportError("ImageComparator requires: pdf2image, Pillow, numpy\npip install pdf2image Pillow numpy")
        self.dpi = dpi
        self.threshold = threshold
        self.blur_radius = blur_radius
        self.save_masks = save_masks
        self.mask_dir = Path(mask_dir) if mask_dir else Path(tempfile.gettempdir())

    def compare(self, pdf_a: str, pdf_b: str) -> ComparatorResult:
        pages_a = _rasterise(pdf_a, self.dpi)
        pages_b = _rasterise(pdf_b, self.dpi)

        diffs: list[Diff] = []
        scores: list[float] = []
        n_pages = max(len(pages_a), len(pages_b))

        for i in range(n_pages):
            if i >= len(pages_a) or i >= len(pages_b):
                scores.append(0.0)
                diffs.append(
                    self._missing_page_diff(
                        i,
                        in_a=(i < len(pages_a)),
                        img=pages_a[i] if i < len(pages_a) else pages_b[i],
                    )
                )
                continue

            masks = _build_masks(pages_a[i], pages_b[i], self.blur_radius, self.threshold)
            raw = masks["raw_diff_ratio"]
            amp = _amplify(raw)
            scores.append(1.0 - amp)

            if raw == 0.0:
                continue

            # Save masks if requested
            paths: dict[str, str | None] = {
                "mask_diff": None,
                "mask_added": None,
                "mask_removed": None,
                "mask_overlay": None,
            }
            if self.save_masks:
                self.mask_dir.mkdir(parents=True, exist_ok=True)
                base = self.mask_dir / f"page{i + 1}"
                _save_mask(masks["diff_mask"], str(base) + "_diff.png", "L")
                _save_mask(masks["added_mask"], str(base) + "_added.png", "L")
                _save_mask(masks["removed_mask"], str(base) + "_removed.png", "L")
                _save_mask(masks["overlay_rgba"], str(base) + "_overlay.png", "RGBA")
                paths = {
                    "mask_diff": str(base) + "_diff.png",
                    "mask_added": str(base) + "_added.png",
                    "mask_removed": str(base) + "_removed.png",
                    "mask_overlay": str(base) + "_overlay.png",
                }

            w, h = pages_a[i].size
            diffs.append(
                Diff(
                    diff_type=DiffType.CHANGED,
                    location_a=Location(page=i, x0=0.0, y0=0.0, x1=1.0, y1=1.0),
                    location_b=Location(page=i, x0=0.0, y0=0.0, x1=1.0, y1=1.0),
                    description=(
                        f"Page {i + 1}: {masks['added_ratio']:.2%} added, "
                        f"{masks['removed_ratio']:.2%} removed "
                        f"→ amplified diff {amp:.2%}"
                    ),
                    payload={
                        "raw_diff_ratio": round(raw, 6),
                        "amplified_diff": round(amp, 6),
                        "added_ratio": round(masks["added_ratio"], 6),
                        "removed_ratio": round(masks["removed_ratio"], 6),
                        "threshold": self.threshold,
                        "dpi": self.dpi,
                        "page_width_px": w,
                        "page_height_px": h,
                        **paths,
                    },
                )
            )

        overall = sum(scores) / len(scores) if scores else 1.0
        return ComparatorResult(
            comparator_id=self.comparator_id,
            similarity=overall,
            diffs=diffs,
            meta={
                "pages_a": len(pages_a),
                "pages_b": len(pages_b),
                "dpi": self.dpi,
                "threshold": self.threshold,
                "amplification_k": AMPLIFICATION_K,
            },
        )

    def _missing_page_diff(self, page_index: int, in_a: bool, img: "Image.Image") -> Diff:
        w, h = img.size
        loc = Location(page=page_index, x0=0.0, y0=0.0, x1=1.0, y1=1.0)
        return Diff(
            diff_type=DiffType.REMOVED if in_a else DiffType.ADDED,
            location_a=loc if in_a else None,
            location_b=loc if not in_a else None,
            description=f"Page {page_index + 1} present only in {'A' if in_a else 'B'}",
            payload={
                "raw_diff_ratio": 1.0,
                "amplified_diff": 1.0,
                "added_ratio": 0.0 if in_a else 1.0,
                "removed_ratio": 1.0 if in_a else 0.0,
                "page_width_px": w,
                "page_height_px": h,
            },
        )
