"""
Core processing engine: reads each raw data file listed in the coding
sheet, applies per-item operations (rename / map / der1), runs QC checks,
and collects the results into a nested dict keyed by KeyList.
"""

import ast
import pandas as pd
import numpy as np


def preCleaning(cleaning_df, x, file):
    """
    Apply any pre-cleaning 'remove'/'change' operations from cleaning_df
    that target `file`, to the raw dataframe `x`, before per-item
    processing.
    """
    d = cleaning_df.copy()
    use_rows = d[d.File == file].index
    if len(use_rows) > 0:
        for r in use_rows:
            (operation, action) = d['Operation'][r], d['Action'][r]
            if operation == 'remove':
                remove_rows = eval(action)
                x = x[~x.index.isin(remove_rows)].copy()
            if operation == 'change':
                [i, col] = eval(action.split('->')[0])
                new_value = eval(action.split('->')[1])
                x.loc[i, col] = new_value
            print(f'pre-cleaning: {file}, proprocessing - index {r} [{operation}]')
    return x


def createKeyString(keyList_string):
    """
    Turn a KeyList string like "['participant_id', 'visit_month']" into
    the pandas expression string used to build the composite join key,
    e.g. x["participant_id"].astype("string") + "_and_" + x["visit_month"].astype("string")
    """
    keyList = eval(keyList_string)
    t = []
    for key in keyList:
        t.append(f'x["{key}"].astype("string")')
    return (' + "_and_" + ').join(t)


def load_raw_file(file):
    """
    Read a single raw data file (.xlsx or .csv), applying the same
    na_values handling and daysB rounding used in the original pipeline.
    """
    if '.xlsx' in file:
        x = pd.read_excel(file, na_values=['', ' '])
    elif '.csv' in file:
        x = pd.read_csv(file, na_values=['', ' '])
    else:
        raise ValueError(f"Unrecognized file type for '{file}' (expected .xlsx or .csv)")

    if "daysB" in x.columns:
        x = x[x.daysB.notna()].copy()
        x = x.reset_index(drop=True)
        x.daysB = x.daysB.astype(int).round(-1)

    return x


def process_coding_sheet(d, cleaning_list=None):
    """
    Run the full per-file, per-item processing loop described by the
    coding sheet `d`.

    Parameters
    ----------
    d : pd.DataFrame
        The coding sheet (Sheet1), as loaded from the Google Sheet.
        Must have columns: Item, ItemType, Required, Values, KeyList,
        Operation, Action, File.
    cleaning_list : list, optional
        Rows for the optional pre-cleaning step, each
        [File, Operation, Action, Reason]. Passed through to preCleaning().

    Returns
    -------
    a : dict
        Nested dict: {KeyList string: {Item: pd.Series}}
    processing_errors : list of dict
        One entry per item that failed to process.
    d : pd.DataFrame
        The same coding sheet, with 'N_deleted_duplicates', 'Check', and
        'Describe' columns filled in for every processed row.
    """
    cleaning_list = cleaning_list or []

    keyLists = d.KeyList.unique()
    keyLists = [x for x in keyLists if not pd.isnull(x)]

    a = {keyList: {} for keyList in keyLists}

    files = d.File.unique()
    files = [x for x in files if not pd.isnull(x)]

    processing_errors = []

    for file in files:
        x = load_raw_file(file)

        if len(cleaning_list) > 0:
            cleaning_df = pd.DataFrame(cleaning_list, columns=['File', 'Operation', 'Action', 'Reason'])
            x = preCleaning(cleaning_df, x, file).copy()

        # Precompute, once per KeyList used in this file, which duplicate
        # row to keep (keep the more complete row, i.e. fewest missing
        # values across x), instead of an arbitrary "first row in file".
        n_missing_per_row = x.isna().sum(axis=1)
        completeness_order = n_missing_per_row.sort_values(kind='mergesort').index

        key_info = {}
        for kl in d.KeyList[d.File == file].dropna().unique():
            key_series = eval(createKeyString(kl))
            key_series.name = 'Key'
            key_sorted = key_series.loc[completeness_order]
            dup_sorted = key_sorted.duplicated(keep='first')
            keep_mask = ~dup_sorted.reindex(x.index)

            dup_keys = key_series[~keep_mask]
            n_dup = len(dup_keys)
            if n_dup > 0:
                dupkeys_string = (", ").join(dup_keys.unique())
                rm_obs = f'N={n_dup}|{dupkeys_string}' if len(dupkeys_string) < 30 else f'N={n_dup}|{dupkeys_string[:30]}..'
            else:
                rm_obs = 'None'

            key_info[kl] = {'key_series': key_series, 'keep_mask': keep_mask, 'rm_obs': rm_obs}

        for i in d.index[d.File == file]:
            describe = ''
            check = ''

            (item, itemType, required, values, keyList, operation, action) = (
                d.Item[i], d.ItemType[i], d.Required[i], d.Values[i], d.KeyList[i],
                d.Operation[i], d.Action[i]
            )

            print(file, i, item)

            # Per-item processing is wrapped in try/except so a single bad
            # row (typo'd column name, malformed map/der1 expression,
            # unrecognized operation, etc.) logs an error and moves on to
            # the next item instead of crashing the whole file's run.
            try:
                if operation == 'rename':
                    v = action
                    y = x[v].copy()

                elif operation == 'map':
                    v = action.split('->')[0]
                    mapping = action.split('->')[1]
                    y = x[v].map(eval(mapping)).copy()
                    NAed = pd.isna(y)
                    if sum(NAed) > 0:
                        NAed_values = x[v][NAed].unique()
                        NAed_values_nonnan = [str(x) for x in NAed_values if str(x) != 'nan']
                        if len(NAed_values_nonnan) > 0:
                            check = check + f"[{{{','.join(NAed_values_nonnan)}}}->NA]"

                elif operation == 'der1':
                    y = eval(action).copy()

                else:
                    raise ValueError(f"Unrecognized operation '{operation}' for item '{item}'")

                y = pd.Series(y)

                # Key for joining -> use the precomputed, completeness-based
                # dedup info for this item's KeyList instead of recomputing
                # keep='first'.
                info = key_info[keyList]
                rm_obs = info['rm_obs']
                keeps = info['keep_mask']
                y = y[keeps].copy()
                y.index = info['key_series'][keeps]

                # remove NAs
                n_original = len(y)
                y = y.dropna().copy()
                n_miss = n_original - len(y)

                # coerce item type
                if itemType == 'string':
                    y = y.astype('string')
                if itemType in ['numeric', 'integer']:
                    y = pd.to_numeric(y, errors='coerce')

                # "Required" check
                if required == 'required':
                    if n_miss > 0:
                        check = f'[{n_miss} fail requirement] '

                # Value check
                if (itemType == 'string') & (pd.notna(values)):
                    allowed_values = ast.literal_eval(str(values))
                    undefined_values = np.setdiff1d(y.unique(), allowed_values)
                    v_counts = (' ').join(f'{y.value_counts()}'.replace('\n', ', ').split(", Name")[0].split())
                    describe = f"N[{n_original}];NMISS[{n_miss}];{v_counts}"
                    if len(undefined_values) > 0:
                        check = check + "[Undefined value: " + (',').join(undefined_values) + ']'

                elif itemType in ['numeric', 'integer']:
                    # Restrict eval's builtins instead of running the Values
                    # range expression with full access to the global
                    # namespace -> narrows (does not eliminate) the risk
                    # from a malformed or malicious coding-sheet entry,
                    # while keeping the flexible "(y>=0) & (y<=30)" syntax.
                    value_check_fail = ~eval(values, {"__builtins__": {}}, {"y": y})
                    n_fail_values = sum(value_check_fail)
                    if n_fail_values > 0:
                        y_fail_value = (',').join(y[value_check_fail].unique().astype('str'))
                        check = check + f"[{n_fail_values} out of range value = {{{y_fail_value}}}]"

                    if len(y) > 0:
                        describe = f"N[{n_original}];NMISS[{n_miss}]; {np.mean(y):.1f} [{min(y):.1f}, {max(y):.1f}]"
                    else:
                        describe = f"N[{n_original}];NMISS[{n_miss}]; Empty Series"

                else:
                    describe = f"N[{n_original}];NMISS[{n_miss}]"

                if check == '':
                    check = 'ok'

                # store y in the nested dictionary
                a[keyList][item] = y

                d.loc[i, 'N_deleted_duplicates'] = rm_obs
                d.loc[i, 'Check'] = check
                d.loc[i, 'Describe'] = describe

            except Exception as e:
                err_msg = f"[ERROR: {type(e).__name__}: {e}]"
                print(f"  !! FAILED to process '{item}' from '{file}' (operation={operation}, action={action}): {e}")
                processing_errors.append({
                    'File': file, 'Item': item, 'Operation': operation,
                    'Action': action, 'Error': f"{type(e).__name__}: {e}"
                })
                d.loc[i, 'N_deleted_duplicates'] = 'ERROR'
                d.loc[i, 'Check'] = err_msg
                d.loc[i, 'Describe'] = ''
                continue

    return a, processing_errors, d
