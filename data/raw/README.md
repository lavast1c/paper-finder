# data/raw/

Put downloaded CIE past-paper PDFs here, **with their original filenames**, e.g.:

```
9702_s23_qp_12.pdf
9702_s23_ms_12.pdf
```

The pipeline only reads from this folder and never modifies it. The PDFs
themselves are git-ignored (copyright of Cambridge Assessment; personal study use
only) — only this README and a `.gitkeep` are tracked.

After adding or removing files here, run:

```
paper-finder ingest
```

## Filename convention

```
{code}_{session}{yy}_{type}_{paper}{variant}.pdf

code     4 digits     9702 = Physics, 9701 = Chemistry, 9709 = Maths, ...
session  s | w | m     May/June | Oct/Nov | Feb/March
yy       2-digit year  23 -> 2023
type     qp | ms | in | gt | er
paper    1 digit       Physics: 1 = multiple choice, 2 = AS structured, 4 = A2 structured
variant  1 digit       1 / 2 / 3 (regional time zones)
```

## Stage 1 shopping list (download these)

Cambridge International **Physics 9702, Paper 1 (multiple choice)**. Grab the
question paper *and* the matching mark scheme for each:

| Question paper        | Mark scheme           |
|-----------------------|-----------------------|
| `9702_s23_qp_12.pdf`  | `9702_s23_ms_12.pdf`  |
| `9702_w23_qp_12.pdf`  | `9702_w23_ms_12.pdf`  |
| `9702_s24_qp_12.pdf`  | `9702_s24_ms_12.pdf`  |
| `9702_w24_qp_12.pdf`  | `9702_w24_ms_12.pdf`  |
| `9702_s24_qp_11.pdf`  | `9702_s24_ms_11.pdf`  |
| `9702_s24_qp_13.pdf`  | `9702_s24_ms_13.pdf`  |

(The last two variants, 11 and 13, are there to check the pipeline handles
multiple variants of the same session.)

Sources: GCE Guide, PapaCambridge, Physics & Maths Tutor, Dynamic Papers — any
mirror. The filenames are identical everywhere.

## Stage 5 shopping list (structured papers)

To build written-answer (non-MCQ) support, add Physics 9702 structured papers —
question paper *and* mark scheme:

| Question paper       | Mark scheme          | Paper                       |
|----------------------|----------------------|-----------------------------|
| `9702_s26_qp_22.pdf` | `9702_s26_ms_22.pdf` | Paper 2 — AS structured     |
| `9702_s26_qp_42.pdf` | `9702_s26_ms_42.pdf` | Paper 4 — A2 structured     |
