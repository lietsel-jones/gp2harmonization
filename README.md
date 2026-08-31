# Cohort processing pipeline: notebook + scripts

The notebook (`Template_script_refactored.ipynb`) imports its logic
from a local `code/` package instead of defining functions inline.
This makes each piece independently testable/reusable and keeps the
notebook focused on the run-specific bits (which sheet, which cohort,
which files).

## Layout

```
Template_script_refactored.ipynb
code/
    __init__.py
    sheets_io.py          get_pygsheets_client(), ReplaceSheet()
    qc_utils.py            checkDup(), checkNull(), TakeOneEntry()
    coding_sheet_lint.py    lint_coding_sheet(), print_lint_results()
    processing.py          preCleaning(), createKeyString(), load_raw_file(),
                            process_coding_sheet()   <- the main per-file/
                            per-item processing loop, now a single function
    merge_keylists.py       merge_keylist_groups()   <- the KeyList merge step
    manifest.py             build_manifest(), save_manifest(), log_run_to_sheet()
```

Keep `code/` next to the notebook. In Colab specifically, the notebook
itself doesn't live on the local filesystem, so cell 2 (right after the
`pip install pygsheets` cell) clones the repo and `cd`s into it:

```python
REPO_URL = 'https://github.com/<your-org>/<your-repo>.git'  # <- set this
REPO_DIR = '<your-repo>'
if not os.path.isdir(REPO_DIR):
    !git clone {REPO_URL}
os.chdir(REPO_DIR)
```

Fill in `REPO_URL`/`REPO_DIR`. The next
cell then adds the (now current) working directory to `sys.path` so
`from code.sheets_io import ...` etc. resolve. It points at the repo
root, not at `code/` itself, since `code/` needs to be importable as
a package (it has an `__init__.py`).

If you're not on Colab (running locally, or the repo is already mounted
in Drive), skip/edit the clone cell and just make sure you're running the
notebook from the repo root.

## What moved where

- **`ReplaceSheet`** (was cell 4) → `code/sheets_io.py`. Also added
  `get_pygsheets_client()`, wrapping the Colab auth boilerplate that was
  cell 3.
- **`checkDup` / `checkNull` / `TakeOneEntry`** (was cell 15) →
  `code/qc_utils.py`. `checkNull` takes an `id_col` parameter now
  (defaults to `'fox_insight_id'` to match the original behavior) so it
  isn't hardcoded to one cohort's ID column.
- **`lint_coding_sheet`** (was cell 25) → `code/coding_sheet_lint.py`.
- **The big per-file/per-item processing loop** (was cells 23 + 26, never
  a function before) → `code/processing.py::process_coding_sheet(d, cleaning_list)`.
  Returns `(a, processing_errors, d)`. `preCleaning`, `createKeyString`,
  and a new `load_raw_file()` helper (the `.csv`/`.xlsx` reading + `daysB`
  rounding logic) live in the same module.
- **The KeyList merge step** (was cell 30, also never a function) →
  `code/merge_keylists.py::merge_keylist_groups(a)`. Returns `(x, b)`.
- **Manifest + run-log** (was cell 32) →
  `code/manifest.py::build_manifest()`, `save_manifest()`,
  `log_run_to_sheet()`.
