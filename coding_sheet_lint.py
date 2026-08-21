"""
Pre-flight validation for the cohort coding sheet, run before spending
time processing raw data files.
"""

import ast
import pandas as pd


def lint_coding_sheet(d):
    """
    Sheet-only validation (no raw data files touched): confirms every
    active row ('Operation' filled in) has parseable Values/KeyList/Action
    syntax and sane categorical fields, so mistakes surface here instead
    of mid-run.

    Returns a list of problem strings (empty list = clean).
    """
    problems = []
    active = d[d['Operation'].notna()].copy()

    valid_operations = {'rename', 'map', 'der1'}
    valid_item_types = {'string', 'numeric', 'integer'}
    valid_required = {'required', 'nullable'}

    seen_items_per_keylist = {}

    for i, row in active.iterrows():
        item = row.get('Item', f'<row {i}>')
        op = row.get('Operation')
        action = row.get('Action')
        values = row.get('Values')
        key_list = row.get('KeyList')
        item_type = row.get('ItemType')
        required = row.get('Required')

        # Operation/Action
        if op not in valid_operations:
            problems.append(f"[{item}] Unrecognized Operation '{op}' (expected one of {sorted(valid_operations)})")
        if pd.isna(action) or str(action).strip() == '':
            problems.append(f"[{item}] Action is empty")
        elif op == 'map' and '->' not in str(action):
            problems.append(f"[{item}] map Action '{action}' is missing the '->' separator")
        elif op == 'map':
            mapping_str = str(action).split('->', 1)[1]
            try:
                mapping = ast.literal_eval(mapping_str)
                if not isinstance(mapping, dict):
                    problems.append(f"[{item}] map Action's mapping is not a dict: {mapping_str}")
            except Exception as e:
                problems.append(f"[{item}] map Action's mapping doesn't parse: {mapping_str} ({e})")
        elif op == 'der1':
            try:
                ast.parse(str(action), mode='eval')
            except SyntaxError as e:
                problems.append(f"[{item}] der1 Action has a syntax error: {action} ({e})")

        # ItemType / Required
        if item_type not in valid_item_types:
            problems.append(f"[{item}] Unrecognized ItemType '{item_type}' (expected one of {sorted(valid_item_types)})")
        if pd.notna(required) and required not in valid_required:
            problems.append(f"[{item}] Unrecognized Required value '{required}' (expected one of {sorted(valid_required)})")

        # Values
        if pd.notna(values):
            if item_type == 'string':
                try:
                    parsed = ast.literal_eval(str(values))
                    if not isinstance(parsed, (list, tuple, set)):
                        problems.append(f"[{item}] string Values should be a list, got: {values}")
                except Exception as e:
                    problems.append(f"[{item}] string Values doesn't parse as a literal list: {values} ({e})")
            elif item_type in ('numeric', 'integer'):
                try:
                    # Syntax-only check against an empty series -> never touches real data
                    eval(str(values), {"__builtins__": {}}, {"y": pd.Series([], dtype=float)})
                except Exception as e:
                    problems.append(f"[{item}] numeric Values expression doesn't evaluate: {values} ({e})")
        elif required == 'required' and item_type in ('numeric', 'integer', 'string'):
            pass  # Values is optional even for required items -> not itself a problem

        # KeyList
        if pd.isna(key_list):
            problems.append(f"[{item}] KeyList is empty")
        else:
            try:
                kl = ast.literal_eval(str(key_list))
                if not isinstance(kl, list) or len(kl) == 0:
                    problems.append(f"[{item}] KeyList should be a non-empty list, got: {key_list}")
                else:
                    seen_items_per_keylist.setdefault(str(key_list), []).append(item)
            except Exception as e:
                problems.append(f"[{item}] KeyList doesn't parse: {key_list} ({e})")

    # Duplicate Item names within the same KeyList would silently overwrite
    # each other in the processing dict (a[keyList][item] = y)
    for kl, items in seen_items_per_keylist.items():
        dupes = {x for x in items if items.count(x) > 1}
        if dupes:
            problems.append(f"KeyList {kl} has duplicate Item name(s) that will overwrite each other: {sorted(dupes)}")

    return problems


def print_lint_results(lint_problems):
    """Pretty-print the output of lint_coding_sheet()."""
    if lint_problems:
        print(f"Coding sheet lint found {len(lint_problems)} issue(s):\n")
        for p in lint_problems:
            print(" -", p)
        print("\nFix these in the coding sheet before continuing - they will "
              "either crash or silently misprocess the affected item(s).")
    else:
        print("Coding sheet lint: no issues found in active rows.")
