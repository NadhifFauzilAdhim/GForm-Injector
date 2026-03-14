# utils/csv_handler.py
# Handles CSV loading, validation, and preview utilities

import io
from typing import Optional

import pandas as pd


def load_csv(uploaded_file) -> Optional[pd.DataFrame]:
    """
    Load a CSV file from a Streamlit UploadedFile object.

    Args:
        uploaded_file: Streamlit UploadedFile object

    Returns:
        pd.DataFrame if successful, None otherwise
    """
    if uploaded_file is None:
        return None

    try:
        # Read raw bytes and decode
        raw_bytes = uploaded_file.read()

        # Try common encodings
        for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                content = raw_bytes.decode(encoding)
                df = pd.read_csv(io.StringIO(content))
                return df
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue

        return None

    except Exception as e:
        raise ValueError(f"Gagal membaca file CSV: {str(e)}")


def get_column_names(df: pd.DataFrame) -> list[str]:
    """
    Return list of column names from a DataFrame.

    Args:
        df: pandas DataFrame

    Returns:
        List of column name strings
    """
    if df is None or df.empty:
        return []
    return list(df.columns)


def get_row_count(df: pd.DataFrame) -> int:
    """
    Return number of data rows in the DataFrame.

    Args:
        df: pandas DataFrame

    Returns:
        Integer row count
    """
    if df is None:
        return 0
    return len(df)


def get_preview(df: pd.DataFrame, n_rows: int = 5) -> pd.DataFrame:
    """
    Return the first n rows of the DataFrame as a preview.

    Args:
        df:     pandas DataFrame
        n_rows: number of rows to preview (default 5)

    Returns:
        Sliced DataFrame
    """
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(n_rows)


def validate_columns(df: pd.DataFrame, required_columns: list[str]) -> dict:
    """
    Check whether required columns exist in the DataFrame.

    Args:
        df:               pandas DataFrame
        required_columns: list of column names that must exist

    Returns:
        dict with keys:
            "valid"   (bool)   – True if all columns are present
            "missing" (list)   – columns that are absent
            "present" (list)   – columns that are present
    """
    if df is None:
        return {"valid": False, "missing": required_columns, "present": []}

    existing = set(df.columns)
    required = set(required_columns)

    missing = sorted(required - existing)
    present = sorted(required & existing)

    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "present": present,
    }


def get_cell_value(row: pd.Series, column: str, fallback: str = "") -> str:
    """
    Safely retrieve a cell value from a DataFrame row as a string.

    Args:
        row:      pandas Series (a single DataFrame row)
        column:   column name to retrieve
        fallback: value to return if the column is missing or the value is NaN

    Returns:
        String representation of the cell value, or fallback
    """
    try:
        val = row[column]
        if pd.isna(val):
            return fallback
        return str(val).strip()
    except (KeyError, TypeError, ValueError):
        return fallback


def dataframe_to_records(df: pd.DataFrame) -> list[dict]:
    """
    Convert a DataFrame to a list of row dictionaries for iteration.

    Args:
        df: pandas DataFrame

    Returns:
        List of dicts, one per row
    """
    if df is None or df.empty:
        return []
    # Fill NaN with empty string so JSON serialisation is safe
    return df.fillna("").to_dict(orient="records")


def get_unique_values(df: pd.DataFrame, column: str) -> list[str]:
    """
    Return sorted unique values for a given column.

    Args:
        df:     pandas DataFrame
        column: column name

    Returns:
        Sorted list of unique string values
    """
    if df is None or column not in df.columns:
        return []
    return sorted(df[column].dropna().astype(str).unique().tolist())


def get_column_stats(df: pd.DataFrame) -> list[dict]:
    """
    Return basic statistics for every column in the DataFrame.

    Args:
        df: pandas DataFrame

    Returns:
        List of dicts with keys: name, dtype, non_null, unique, sample
    """
    if df is None or df.empty:
        return []

    stats = []
    for col in df.columns:
        series = df[col]
        sample_vals = series.dropna().astype(str).head(3).tolist()
        stats.append(
            {
                "name": col,
                "dtype": str(series.dtype),
                "non_null": int(series.notna().sum()),
                "unique": int(series.nunique()),
                "sample": ", ".join(sample_vals) if sample_vals else "-",
            }
        )
    return stats
