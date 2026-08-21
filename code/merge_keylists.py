"""
Merge the per-KeyList processing results (`a`, from process_coding_sheet)
into a single wide dataframe: longitudinal (participant_id + visit_month)
items form the base grain, and static/baseline (participant_id-only)
items are left-merged (broadcast) onto every visit row.
"""

import pandas as pd


def merge_keylist_groups(a):
    """
    Parameters
    ----------
    a : dict
        {KeyList string: {Item: pd.Series}}, as returned by
        process_coding_sheet().

    Returns
    -------
    x : pd.DataFrame
        The final merged dataframe.
    b : dict
        {KeyList string: pd.DataFrame}, the intermediate per-KeyList wide
        dataframes -> kept around in case any 'other_keys' group (more
        than 2 keys) needs a manual merge.
    """
    b = {}
    for k in a.keys():
        keyList = eval(k)
        t = pd.concat(a[k], axis=1)
        t = t.reset_index()  # index was 'Key' -> becomes a column named 'Key'

        if len(keyList) == 2:
            # convention: 2 key groups are (participant_id, visit_month), in that order
            t[['participant_id', 'visit_month']] = t['Key'].str.split('_and_', expand=True)
            t = t.drop(columns='Key')
        elif len(keyList) == 1:
            # single-key groups are static/baseline variables, keyed by participant_id
            t = t.rename(columns={'Key': 'participant_id'})
        else:
            # more than 2 keys isn't covered by the participant_id/visit_month
            # naming convention above -> keep the raw Key column and merge
            # it in manually.
            print(f"NOTE: KeyList {k} has {len(keyList)} keys ({keyList}). "
                  f"No participant_id/visit_month split is defined for this shape - "
                  f"inspect b['{k}'] and merge it in by hand.")
        b[k] = t

    # Use the longitudinal (participant_id + visit_month) group as the base
    # grain, and left-merge single-key (baseline/static) groups onto it so
    # their values are broadcast across every visit row for that participant.
    # If more than one 2-key group exists (unusual -> would mean two
    # different longitudinal files/keys), they're merged together on
    # (participant_id, visit_month) as well, with a warning so you know to
    # sanity-check it.
    longitudinal_keys = [k for k in b if len(eval(k)) == 2]
    static_keys = [k for k in b if len(eval(k)) == 1]
    other_keys = [k for k in b if len(eval(k)) not in (1, 2)]

    if len(longitudinal_keys) > 0:
        x = b[longitudinal_keys[0]]
        if len(longitudinal_keys) > 1:
            print(f"WARNING: {len(longitudinal_keys)} longitudinal (2-key) KeyList "
                  f"groups found: {longitudinal_keys}. Merging them together on "
                  f"(participant_id, visit_month) - double check this is intended.")
            for k in longitudinal_keys[1:]:
                x = x.merge(b[k], on=['participant_id', 'visit_month'], how='outer')
    else:
        # no longitudinal group -> fall back to the first static group as the base
        print("WARNING: no 2-key (participant_id, visit_month) KeyList group found. "
              "Using the first single-key group as the base instead.")
        x = b[static_keys[0]] if static_keys else b[list(b.keys())[0]]
        static_keys = static_keys[1:] if static_keys else []

    for k in static_keys:
        x = x.merge(b[k], on='participant_id', how='left')

    if other_keys:
        print(f"WARNING: {len(other_keys)} KeyList group(s) with an unsupported "
              f"key shape were NOT merged automatically: {other_keys}. "
              f"They are still available in b[...] if you need to merge them by hand.")

    return x, b
