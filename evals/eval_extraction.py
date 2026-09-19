"""
Phase 0.5 eval: measures how much table content survives extraction,
old (pre-fix) vs new (api/utils/extraction.py), on real files.

Methodology: for each table found in a document, we check (a) whether each
individual cell's text appears intact in the extracted output (cell recall),
and (b) whether all of a row's cells land close together in the output
(row cohesion) -- a cell can be present but detached from its row, which
cell recall alone won't catch.

DOCX-only: PDF table-aware extraction was implemented, tested against 3 real
PDFs (identical old-vs-new results on all 3 -- no measurable benefit) and a
controlled synthetic PDF built specifically to test it (PyMuPDF's
find_tables() failed to detect a genuine hand-drawn grid table at all).
Three independent tests showing no proven benefit -> reverted per
IMPROVEMENT_PLAN.md Phase 0.5. extract_pdf is back to plain page.get_text().
The DOCX fix stayed: it fixes a real, unambiguous bug (tables were being
silently dropped entirely, not just imperfectly extracted).
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from docx import Document as DocxDocument

from utils.extraction import extract_docx  # new implementation
from log_experiment import log_result

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "test_docs", "raw_samples")


def old_extract_docx(file_bytes: bytes) -> str:
    """Pre-Phase-0.5 baseline: doc.paragraphs only, tables never walked."""
    doc = DocxDocument(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def get_docx_table_rows(file_bytes: bytes):
    doc = DocxDocument(io.BytesIO(file_bytes))
    rows = []
    for table in doc.tables:
        for row in table.rows:
            rows.append([cell.text.strip() for cell in row.cells if cell.text.strip()])
    return rows


def cell_recall(cells, extracted_text: str) -> float:
    """Fraction of ground-truth cell strings found intact in the extracted text."""
    if not cells:
        return None
    found = sum(1 for c in cells if c in extracted_text)
    return round(found / len(cells) * 100, 1)


def row_cohesion(rows, extracted_text: str, window: int = 300) -> float:
    """
    Fraction of table rows whose cells all land within `window` characters of
    each other in the extracted text. Uses a monotonically advancing search
    cursor instead of a global text.find(cell) per cell, since repeated short
    cell values (blank cells, "$75.00", "1st") would otherwise keep matching
    an earlier unrelated duplicate instead of the cell's actual position.
    """
    rows = [[c for c in row if c and str(c).strip()] for row in rows]
    rows = [row for row in rows if len(row) >= 2]  # single-cell rows can't be "detached"
    if not rows:
        return None

    cohesive = 0
    cursor = 0
    for row in rows:
        positions = []
        row_start_cursor = cursor
        for cell in row:
            idx = extracted_text.find(str(cell).strip(), row_start_cursor)
            if idx == -1:
                positions = None
                break
            positions.append(idx)
        if positions:
            if (max(positions) - min(positions)) <= window:
                cohesive += 1
            cursor = min(positions)  # next row searches forward from this row's earliest match

    return round(cohesive / len(rows) * 100, 1)


def run():
    files = [
        ("docx_synthetic_with_table.docx", "docx"),
        ("docx_synthetic_no_table.docx", "docx"),
    ]

    for filename, filetype in files:
        path = os.path.join(RAW_DIR, filename)
        if not os.path.isfile(path):
            print(f"SKIP (missing): {filename}")
            continue

        with open(path, "rb") as f:
            file_bytes = f.read()

        rows = get_docx_table_rows(file_bytes)
        old_text = old_extract_docx(file_bytes)
        new_text = extract_docx(file_bytes)

        cells = [c for row in rows for c in row]
        old_recall = cell_recall(cells, old_text)
        new_recall = cell_recall(cells, new_text)
        old_cohesion = row_cohesion(rows, old_text)
        new_cohesion = row_cohesion(rows, new_text)

        print(f"\n{filename}: {len(cells)} table cells / {len(rows)} rows in source")
        print(f"  cell recall   -- old: {old_recall}%   new: {new_recall}%")
        print(f"  row cohesion  -- old: {old_cohesion}%   new: {new_cohesion}%")

        if not cells:
            log_result("phase_0.5_table_extraction", "old", "table_cells_in_source", 0,
                        notes=f"{filename}: no tables in this document (control case)")
            log_result("phase_0.5_table_extraction", "new", "table_cells_in_source", 0,
                        notes=f"{filename}: no tables in this document (control case)")
            continue

        log_result("phase_0.5_table_extraction", "old", "table_cell_recall_pct", old_recall,
                    notes=f"{filename}: {len(cells)} ground-truth cells")
        log_result("phase_0.5_table_extraction", "new", "table_cell_recall_pct", new_recall,
                    notes=f"{filename}: {len(cells)} ground-truth cells")
        if old_cohesion is not None:
            log_result("phase_0.5_table_extraction", "old", "row_cohesion_pct", old_cohesion,
                        notes=f"{filename}: {len(rows)} rows, window=300 chars")
            log_result("phase_0.5_table_extraction", "new", "row_cohesion_pct", new_cohesion,
                        notes=f"{filename}: {len(rows)} rows, window=300 chars")


if __name__ == "__main__":
    run()
