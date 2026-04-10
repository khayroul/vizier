"""Convert PDF templates into per-page PNG exemplars.

Usage:
    # Single PDF → posters collection
    python3 scripts/pdf_to_exemplars.py path/to/template.pdf --collection posters

    # All PDFs in a folder → layouts collection
    python3 scripts/pdf_to_exemplars.py path/to/folder/ --collection layouts

    # Specific pages only (1-indexed)
    python3 scripts/pdf_to_exemplars.py book.pdf --collection layouts --pages 1,3,5,8,12

    # Custom DPI (default 200, higher = sharper but bigger files)
    python3 scripts/pdf_to_exemplars.py poster.pdf --collection posters --dpi 300

Output:
    datasets/operator_exemplars/{collection}/{pdf_stem}_p{N}.png

Notes:
    - Single-page PDFs (posters/flyers): produces one PNG
    - Multi-page PDFs (books/magazines): produces one PNG per page/spread
    - Use --pages to pick only the representative spreads you want
    - Landscape pages are kept as-is (spread view)
    - All PNGs ready for ingestion by scripts/ingest_operator_exemplars.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

EXEMPLAR_ROOT = Path(__file__).resolve().parent.parent / "datasets" / "operator_exemplars"
VALID_COLLECTIONS = {"posters", "layouts", "brochures", "textures"}
DEFAULT_DPI = 200  # sharp enough for NIMA + CLIP, not wasteful


def render_pdf_pages(
    pdf_path: Path,
    collection: str,
    pages: list[int] | None = None,
    dpi: int = DEFAULT_DPI,
) -> list[Path]:
    """Render selected pages of a PDF as PNG files.

    Args:
        pdf_path: Path to the PDF file.
        collection: Target collection directory (posters, layouts, brochures, textures).
        pages: 1-indexed page numbers to render. None = all pages.
        dpi: Resolution for rendering. 200 is good for NIMA/CLIP. 300 for print-quality.

    Returns:
        List of paths to the generated PNG files.
    """
    if collection not in VALID_COLLECTIONS:
        raise ValueError(
            f"Collection must be one of {VALID_COLLECTIONS}, got '{collection}'"
        )

    output_dir = EXEMPLAR_ROOT / collection
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    stem = pdf_path.stem.replace(" ", "_").lower()
    total_pages = len(doc)

    # Resolve page indices (convert 1-indexed to 0-indexed)
    if pages is not None:
        page_indices = [p - 1 for p in pages if 0 < p <= total_pages]
        if not page_indices:
            logger.warning("No valid pages in %s (total: %d)", pdf_path.name, total_pages)
            doc.close()
            return []
    else:
        page_indices = list(range(total_pages))

    zoom = dpi / 72  # PDF default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)

    output_paths: list[Path] = []
    for idx in page_indices:
        page = doc[idx]
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        page_num = idx + 1
        out_path = output_dir / f"{stem}_p{page_num:03d}.png"
        pix.save(str(out_path))
        output_paths.append(out_path)

        width_px = pix.width
        height_px = pix.height
        orientation = "landscape" if width_px > height_px else "portrait"
        logger.info(
            "  Page %d/%d → %s (%dx%d, %s)",
            page_num, total_pages, out_path.name, width_px, height_px, orientation,
        )

    doc.close()
    return output_paths


def process_input(
    input_path: Path,
    collection: str,
    pages: list[int] | None = None,
    dpi: int = DEFAULT_DPI,
) -> list[Path]:
    """Process a single PDF or all PDFs in a directory.

    Args:
        input_path: Path to a PDF file or directory containing PDFs.
        collection: Target collection directory.
        pages: Page filter (only applies to individual PDFs, not batch).
        dpi: Rendering resolution.

    Returns:
        List of all generated PNG paths.
    """
    all_outputs: list[Path] = []

    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        logger.info("Processing: %s", input_path.name)
        outputs = render_pdf_pages(input_path, collection, pages, dpi)
        all_outputs.extend(outputs)

    elif input_path.is_dir():
        pdfs = sorted(input_path.glob("*.pdf"))
        if not pdfs:
            logger.warning("No PDF files found in %s", input_path)
            return []

        logger.info("Found %d PDFs in %s", len(pdfs), input_path)
        for pdf in pdfs:
            logger.info("Processing: %s", pdf.name)
            # When batch processing, render all pages (ignore --pages flag)
            outputs = render_pdf_pages(pdf, collection, pages=None, dpi=dpi)
            all_outputs.extend(outputs)

    else:
        logger.error("Input must be a PDF file or directory: %s", input_path)
        return []

    return all_outputs


def _parse_pages(pages_str: str) -> list[int]:
    """Parse comma-separated page numbers and ranges.

    Examples:
        "1,3,5"     → [1, 3, 5]
        "1-5"       → [1, 2, 3, 4, 5]
        "1,3-5,8"   → [1, 3, 4, 5, 8]
    """
    result: list[int] = []
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            result.extend(range(int(start), int(end) + 1))
        else:
            result.append(int(part))
    return sorted(set(result))


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert PDF templates into per-page PNG exemplars.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input",
        type=Path,
        help="PDF file or directory containing PDFs",
    )
    parser.add_argument(
        "--collection",
        required=True,
        choices=sorted(VALID_COLLECTIONS),
        help="Target exemplar collection",
    )
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="Comma-separated page numbers or ranges to render (1-indexed). "
        "E.g. '1,3,5' or '1-5,8,12'. Default: all pages.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help=f"Rendering resolution (default: {DEFAULT_DPI})",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    pages = _parse_pages(args.pages) if args.pages else None
    outputs = process_input(args.input, args.collection, pages, args.dpi)

    if outputs:
        logger.info("\nDone. %d PNGs → datasets/operator_exemplars/%s/", len(outputs), args.collection)
    else:
        logger.warning("\nNo PNGs generated.")
        sys.exit(1)


if __name__ == "__main__":
    main()
