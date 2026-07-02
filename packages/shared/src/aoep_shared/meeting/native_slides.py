"""Render source PDF/PPTX pages as synced slide images (alternative to bullet HTML)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional


def _pymupdf_available() -> bool:
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def _pdftoppm_available() -> bool:
    return shutil.which("pdftoppm") is not None


def _soffice_available() -> bool:
    for name in ("soffice", "libreoffice"):
        if shutil.which(name):
            return True
    return False


def _soffice_bin() -> str:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    return "soffice"


def pptx_to_pdf(pptx_path: Path, out_dir: Path) -> Path:
    """Convert PPTX to PDF via LibreOffice headless (when installed)."""
    pptx_path = Path(pptx_path)
    if not pptx_path.is_file():
        raise FileNotFoundError(pptx_path)
    if pptx_path.suffix.lower() != ".pptx":
        raise ValueError(f"expected .pptx, got {pptx_path.suffix}")
    if not _soffice_available():
        raise RuntimeError(
            "PPTX native slides need LibreOffice (soffice --headless). "
            "Install LibreOffice, export the deck to PDF, and pass --slide-source file.pdf"
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [_soffice_bin(), "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx_path)],
        check=True,
        timeout=180,
        capture_output=True,
    )
    pdf = out_dir / f"{pptx_path.stem}.pdf"
    if not pdf.is_file():
        pdfs = sorted(out_dir.glob("*.pdf"))
        if not pdfs:
            raise RuntimeError(f"LibreOffice did not produce a PDF for {pptx_path}")
        pdf = pdfs[-1]
    return pdf


def render_pdf_pages(pdf_path: Path, out_dir: Path, *, dpi: int = 144) -> List[Path]:
    """Render each PDF page to a PNG under ``out_dir/pages/``."""
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    pages_dir = Path(out_dir) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for old in pages_dir.glob("page-*.png"):
        old.unlink(missing_ok=True)

    if _pymupdf_available():
        import fitz

        doc = fitz.open(str(pdf_path))
        scale = dpi / 72.0
        matrix = fitz.Matrix(scale, scale)
        paths: List[Path] = []
        for i in range(len(doc)):
            pix = doc[i].get_pixmap(matrix=matrix, alpha=False)
            dest = pages_dir / f"page-{i + 1:03d}.png"
            pix.save(str(dest))
            paths.append(dest)
        doc.close()
        return paths

    if _pdftoppm_available():
        prefix = str(pages_dir / "page")
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), prefix],
            check=True,
            timeout=300,
            capture_output=True,
        )
        raw = sorted(pages_dir.glob("page-*.png"))
        paths: List[Path] = []
        for i, src in enumerate(raw, start=1):
            dest = pages_dir / f"page-{i:03d}.png"
            if src != dest:
                if dest.exists():
                    dest.unlink()
                src.rename(dest)
            paths.append(dest)
        return paths

    raise RuntimeError(
        "PDF native slides need PyMuPDF (pip install pymupdf) or poppler pdftoppm. "
        "Or use the default HTML slide deck (omit --slide-source)."
    )


def prepare_native_slides(source: Path, out_dir: Path, *, dpi: int = 144) -> List[Path]:
    """Prepare ordered PNGs from a PDF or PPTX source file."""
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(source)
    ext = source.suffix.lower()
    if ext == ".pptx":
        pdf = pptx_to_pdf(source, out_dir / "_convert")
        return render_pdf_pages(pdf, out_dir, dpi=dpi)
    if ext == ".pdf":
        return render_pdf_pages(source, out_dir, dpi=dpi)
    raise ValueError(
        f"unsupported slide source {ext!r}; use .pdf or .pptx (or omit --slide-source for HTML)"
    )


def page_for_step(slide_index: int, page_count: int) -> int:
    """Map a lesson slide index onto a native page (0-based)."""
    if page_count <= 0:
        return 0
    return max(0, min(slide_index, page_count - 1))


def native_slide_status() -> dict:
    return {
        "pymupdf": _pymupdf_available(),
        "pdftoppm": _pdftoppm_available(),
        "libreoffice": _soffice_available(),
    }
