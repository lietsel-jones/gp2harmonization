"""
Helpers for reading from / writing to Google Sheets via pygsheets.
"""

import pygsheets


def get_pygsheets_client():
    """
    Authenticate and return a pygsheets client.
    Only works inside Google Colab (uses google.colab.auth under the hood).
    """
    import google.auth
    from google.colab import auth

    auth.authenticate_user()
    credentials, _ = google.auth.default()
    return pygsheets.client.Client(credentials)


def ReplaceSheet(file, sheet_name, sheet_df, start="A1", ch=True):
    """
    Overwrite `sheet_name` in the given pygsheets `file` (spreadsheet) with
    `sheet_df`. Creates the worksheet first if it doesn't already exist.
    """
    try:
        worksheet = file.worksheet_by_title(sheet_name)
        worksheet.set_dataframe(sheet_df, start=start, fit=True, nan='', copy_head=ch)
        print(f"{sheet_name} has been overwritten")
    except pygsheets.WorksheetNotFound:
        print(f"{sheet_name} not found, adding sheet instead")
        file.add_worksheet(sheet_name)
        worksheet = file.worksheet_by_title(sheet_name)
        worksheet.set_dataframe(sheet_df, start=start, fit=True, nan='', copy_head=ch)
