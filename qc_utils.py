"""
QC utility functions for checking duplicates and nulls, and for collapsing
duplicate rows down to a single "best" observation per key.
"""

import pandas as pd


def checkDup(df, keys):
    """
    Check for duplicated observations by `keys`.

    keys : list of str
        Column name(s) that should uniquely identify a row,
        e.g. ['PATNO', 'EVENT_ID']

    Returns the duplicated rows (sorted by keys) if any are found,
    otherwise returns None and just prints a summary.
    """
    t = df[keys]
    t_dup = t[t.duplicated()]
    n_dup = len(t_dup)
    if n_dup == 0:
        print(f'{len(df)} entries: No duplication')
    if n_dup > 0:
        d_dup2 = df[df.duplicated(keep=False, subset=keys)].sort_values(keys)
        print(f'{len(df)} entries: {len(d_dup2)} duplicated entries are returned')
        return d_dup2


def checkNull(df, voi, id_col='fox_insight_id'):
    """
    Check for null values in `voi` (variable of interest) and return all
    rows sharing an id (`id_col`) with a null observation, so nulls can be
    reviewed in context.

    id_col defaults to 'fox_insight_id' to match the original behavior;
    pass a different id_col for other cohorts.
    """
    nulls = df[df.loc[:, voi].isnull()]
    id_w_null = nulls[id_col]
    dat_w_null = df[df[id_col].isin(id_w_null)]
    n_null = len(nulls)

    if n_null == 0:
        print(f'{len(df)} entries: No null values')
    if n_null > 0:
        print(f'{len(df)} entries: {n_null} null entries are returned')
        return dat_w_null


def TakeOneEntry(df, key, method='less_na'):
    """
    Collapse duplicate rows (by `key`, a list of column names) down to one
    row each.

    method='less_na' (default): keep the row with the fewest missing values.
    method='ffill': forward-fill missingness within each key group, keep the
        LAST entry. NOTE: sort df into the desired fill order before calling.
    method='bfill': back-fill missingness within each key group, keep the
        FIRST entry. NOTE: sort df into the desired fill order before calling.
    """
    if method == 'less_na':
        df['n_missing'] = pd.isna(df).sum(axis=1)
        df = df.sort_values(key + ['n_missing']).copy()
        df = df.drop_duplicates(subset=key, keep='first')
        df = df.drop(columns=['n_missing']).copy()
    else:
        print('FFILL on process: DO NOT FORGET to sort before using this function!!')
        df.update(df.groupby(key).fillna(method=method))
        df = df.reset_index(drop=True)
        if method == 'ffill':
            df = df.drop_duplicates(subset=key, keep='last').copy()
        if method == 'bfill':
            df = df.drop_duplicates(subset=key, keep='first').copy()

    return df
