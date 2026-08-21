"""
Build and persist a run manifest (provenance record) for a processing run,
and optionally append a summary row to the coding sheet's 'run_log' tab.
"""

import json
import getpass
from datetime import datetime


def build_manifest(cohort, sheet, ref_dictionary_path, ref, d, processing_errors,
                    output_path, output_shape):
    """
    Assemble the run manifest dict. Does not write anything to disk.
    """
    manifest = {
        'cohort': cohort,
        'run_timestamp': datetime.now().isoformat(timespec='seconds'),
        'coding_sheet_key': sheet.id,
        'coding_sheet_url': sheet.url if hasattr(sheet, 'url') else None,
        'ref_dictionary_path': ref_dictionary_path,
        'ref_dictionary_shape': list(ref.shape),
        'n_active_items': int(d['Operation'].notna().sum()),
        'n_processing_errors': len(processing_errors),
        'output_path': output_path,
        'output_shape': list(output_shape),
        'run_by': getpass.getuser() if hasattr(getpass, 'getuser') else None,
    }
    return manifest


def save_manifest(manifest, output_path):
    """
    Write the manifest to <output_path>_manifest.json (replacing the .csv
    extension), and return the path written to.
    """
    manifest_path = output_path.replace('.csv', '_manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to {manifest_path}")
    return manifest_path


def log_run_to_sheet(sheet, manifest, new_sheet='run_log'):
    """
    Append a summary row of `manifest` to the coding sheet's `new_sheet`
    tab, creating the tab (with a header row) if it doesn't exist yet.
    Never raises -> a failure here shouldn't lose a completed run, since
    the local manifest file already has the provenance.
    """
    try:
        try:
            log_ws = sheet.worksheet_by_title(new_sheet)
        except Exception:
            log_ws = sheet.add_worksheet(new_sheet)
            log_ws.update_row(1, list(manifest.keys()))  # header row on first creation

        next_row = len(log_ws.get_all_values(include_tailing_empty=False, include_tailing_empty_rows=False)) + 1
        if next_row > log_ws.rows:
            log_ws.add_rows(next_row - log_ws.rows)

        log_ws.update_row(next_row, [str(v) for v in manifest.values()])
        print(f"Run appended to the coding sheet's '{new_sheet}' tab (row {next_row}).")
    except Exception as e:
        print(f"NOTE: could not append to the coding sheet's run_log tab ({type(e).__name__}: {e}). "
              f"The local manifest still has this run's provenance.")
