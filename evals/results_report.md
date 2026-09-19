# ClauseIQ Eval Results

## phase_0.5_table_extraction

| Date | Strategy | Metric | Value | Tokens | Latency (ms) | Notes |
|---|---|---|---|---|---|---|
| 2026-07-29 | old | table_cell_recall_pct | 0.0 |  |  | docx_synthetic_with_table.docx: 9 ground-truth cells |
| 2026-07-29 | new | table_cell_recall_pct | 100.0 |  |  | docx_synthetic_with_table.docx: 9 ground-truth cells |
| 2026-07-29 | old | row_cohesion_pct | 0.0 |  |  | docx_synthetic_with_table.docx: 3 rows, window=300 chars |
| 2026-07-29 | new | row_cohesion_pct | 100.0 |  |  | docx_synthetic_with_table.docx: 3 rows, window=300 chars |
| 2026-07-29 | old | table_cells_in_source | 0 |  |  | docx_synthetic_no_table.docx: no tables in this document (control case) |
| 2026-07-29 | new | table_cells_in_source | 0 |  |  | docx_synthetic_no_table.docx: no tables in this document (control case) |
| 2026-07-29 | pdf_find_tables (reverted) | row_cohesion_pct | no_benefit |  |  | Tested on 3 real PDFs (identical old/new results) + 1 controlled synthetic PDF (find_tables failed to detect a genuine hand-drawn table). No measurable benefit across all 4 tests -- reverted extract_pdf to plain page.get_text(). |

## phase_1_chunking_comparison

| Date | Strategy | Metric | Value | Tokens | Latency (ms) | Notes |
|---|---|---|---|---|---|---|
| 2026-07-29 | fixed | retrieval_hit_rate_pct | 93.5 |  |  | doc=doc1, 45 chunks, avg_chunk_size=1292 chars |
| 2026-07-29 | semantic | retrieval_hit_rate_pct | 90.3 |  |  | doc=doc1, 35 chunks, avg_chunk_size=1403 chars |
| 2026-07-29 | fixed | retrieval_hit_rate_pct | 93.8 |  |  | doc=openai, 18 chunks, avg_chunk_size=1332 chars |
| 2026-07-29 | semantic | retrieval_hit_rate_pct | 87.5 |  |  | doc=openai, 17 chunks, avg_chunk_size=1206 chars |
| 2026-07-29 | fixed | retrieval_hit_rate_pct | 78.3 |  |  | doc=nda1, 26 chunks, avg_chunk_size=1371 chars |
| 2026-07-29 | semantic | retrieval_hit_rate_pct | 78.3 |  |  | doc=nda1, 20 chunks, avg_chunk_size=1526 chars |
| 2026-07-29 | fixed | retrieval_hit_rate_pct | 84.0 |  |  | doc=service1, 32 chunks, avg_chunk_size=1332 chars |
| 2026-07-29 | semantic | retrieval_hit_rate_pct | 80.0 |  |  | doc=service1, 25 chunks, avg_chunk_size=1450 chars |
| 2026-07-29 | fixed | retrieval_hit_rate_pct | 96.4 |  |  | doc=unstructured (unstructured prose, no headers/numbering), 28 chunks, avg_chunk_size=1353 chars |
| 2026-07-29 | semantic | retrieval_hit_rate_pct | 89.3 |  |  | doc=unstructured (unstructured prose, no headers/numbering), 25 chunks, avg_chunk_size=1298 chars |
