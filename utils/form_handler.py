# utils/form_handler.py
# Handles payload building and HTTP POST submission to Google Form endpoints

import random
import time
from datetime import datetime
from typing import Optional

import requests

from utils.csv_handler import get_cell_value
from utils.generators import call_generator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://docs.google.com/",
    "Origin": "https://docs.google.com",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Source mode constants
MODE_CSV = "CSV Column"
MODE_STATIC = "Static Value"
MODE_GENERATOR = "Random Generator"

ALL_MODES = [MODE_CSV, MODE_STATIC, MODE_GENERATOR]


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------


def build_payload(
    row: dict,
    mappings: list[dict],
    fvv: str = "1",
    page_history: str = "0",
    include_sentinels: bool = True,
) -> dict:
    """
    Build a Google Form POST payload from a single CSV row and mapping config.

    Each mapping entry is a dict with keys:
        entry_id   (str)  – e.g. "entry.976363616"
        mode       (str)  – one of MODE_CSV / MODE_STATIC / MODE_GENERATOR
        value      (str)  – CSV column name, static value, or generator name
        sentinel   (bool) – whether to add an _sentinel field for this entry

    Args:
        row:               Single row dict from the CSV (column -> value).
        mappings:          List of mapping dicts as described above.
        fvv:               Google Form version flag (usually "1").
        page_history:      Comma-separated page indices visited (e.g. "0,1,2").
        include_sentinels: When True, append empty _sentinel keys for entries
                           that have sentinel=True in their mapping config.

    Returns:
        dict ready to be passed as ``data=`` in requests.post().
    """
    payload: dict[str, str] = {}

    for mapping in mappings:
        entry_id: str = mapping.get("entry_id", "").strip()
        mode: str = mapping.get("mode", MODE_CSV)
        value: str = mapping.get("value", "")
        add_sentinel: bool = mapping.get("sentinel", False)

        if not entry_id:
            continue

        if mode == MODE_CSV:
            cell_val = get_cell_value(_dict_to_series(row), column=value, fallback="")
            resolved = cell_val
        elif mode == MODE_STATIC:
            resolved = str(value)
        elif mode == MODE_GENERATOR:
            resolved = call_generator(value)
        else:
            resolved = str(value)

        key = _normalise_entry_id(entry_id)
        payload[key] = resolved

        if include_sentinels and add_sentinel:
            payload[f"{key}_sentinel"] = ""

    payload["fvv"] = fvv
    payload["pageHistory"] = page_history

    return payload


# ---------------------------------------------------------------------------
# HTTP sender
# ---------------------------------------------------------------------------


def send_form(
    form_url: str,
    payload: dict,
    timeout: int = 15,
) -> dict:
    """
    Send a single POST request to a Google Form response endpoint.

    Args:
        form_url: Full Google Form /formResponse URL.
        payload:  Dict of field names -> values to submit.
        timeout:  Request timeout in seconds.

    Returns:
        dict with keys:
            success  (bool)   – True if submission was accepted
            status   (int)    – HTTP status code (0 if network error)
            message  (str)    – Human-readable result message
            ts       (str)    – Timestamp of the request
    """
    ts = _now_str()

    # Basic URL validation
    if not form_url or "formResponse" not in form_url:
        return {
            "success": False,
            "status": 0,
            "message": "Invalid URL. Make sure it ends with /formResponse",
            "ts": ts,
        }

    try:
        response = requests.post(
            form_url,
            data=payload,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code == 200:
            return {
                "success": True,
                "status": response.status_code,
                "message": "Submission successful",
                "ts": ts,
            }
        else:
            return {
                "success": False,
                "status": response.status_code,
                "message": f"Server responded with status {response.status_code}",
                "ts": ts,
            }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "status": 0,
            "message": "Connection failed. Check your internet connection or the form URL.",
            "ts": ts,
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status": 0,
            "message": f"Request timed out after {timeout} seconds.",
            "ts": ts,
        }
    except requests.exceptions.RequestException as exc:
        return {
            "success": False,
            "status": 0,
            "message": f"Request error: {str(exc)}",
            "ts": ts,
        }


# ---------------------------------------------------------------------------
# Bulk submission runner
# ---------------------------------------------------------------------------


def run_bulk_submit(
    form_url: str,
    records: list[dict],
    mappings: list[dict],
    fvv: str = "1",
    page_history: str = "0",
    include_sentinels: bool = True,
    min_delay: float = 1.0,
    max_delay: float = 3.0,
    progress_callback=None,
    log_callback=None,
    stop_flag: Optional[list] = None,
) -> list[dict]:
    """
    Iterate over CSV records and submit each one to the Google Form.

    Args:
        form_url:          Google Form /formResponse URL.
        records:           List of row dicts from the CSV.
        mappings:          Mapping config list (see build_payload()).
        fvv:               Google Form fvv metadata value.
        page_history:      Google Form pageHistory metadata value.
        include_sentinels: Whether to append _sentinel keys.
        min_delay:         Minimum sleep time between requests (seconds).
        max_delay:         Maximum sleep time between requests (seconds).
        progress_callback: Optional callable(current, total) for the progress bar.
        log_callback:      Optional callable(message: str) for log output.
        stop_flag:         Optional single-element list; set stop_flag[0]=True
                           from outside to abort the loop cleanly.

    Returns:
        List of result dicts (one per record), each from send_form().
        Each result also contains:
            row_index (int)  – 0-based index of the row in ``records``
            payload   (dict) – the payload that was sent
    """
    results: list[dict] = []
    total = len(records)

    if stop_flag is None:
        stop_flag = [False]

    for idx, row in enumerate(records):
        # Honour external stop signal
        if stop_flag[0]:
            _log(
                log_callback,
                f"[{_now_str()}] ⏹️  Process stopped by user at row {idx + 1}/{total}",
            )
            break

        # Build payload for this row
        payload = build_payload(
            row=row,
            mappings=mappings,
            fvv=fvv,
            page_history=page_history,
            include_sentinels=include_sentinels,
        )

        # Send the request
        result = send_form(form_url, payload)
        result["row_index"] = idx
        result["payload"] = payload
        results.append(result)

        # Emit log entry
        icon = "✅" if result["success"] else "❌"
        _log(
            log_callback,
            f"[{result['ts']}] {icon} Row {idx + 1}/{total} — {result['message']}",
        )

        # Update progress bar
        if progress_callback:
            try:
                progress_callback(idx + 1, total)
            except Exception:
                pass

        # Delay between requests (skip after the last record)
        if idx < total - 1 and not stop_flag[0]:
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)

    return results


# ---------------------------------------------------------------------------
# Result summariser
# ---------------------------------------------------------------------------


def summarise_results(results: list[dict]) -> dict:
    """
    Aggregate bulk-submission results into a summary dict.

    Args:
        results: List of result dicts returned by run_bulk_submit().

    Returns:
        dict with keys:
            total   (int)   – total records processed
            success (int)   – number of successful submissions
            failed  (int)   – number of failed submissions
            rate    (float) – success rate as a fraction (0.0 – 1.0)
    """
    total = len(results)
    success = sum(1 for r in results if r.get("success"))
    failed = total - success
    rate = (success / total) if total > 0 else 0.0

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "rate": rate,
    }


# ---------------------------------------------------------------------------
# Mapping validation helpers
# ---------------------------------------------------------------------------


def validate_mappings(mappings: list[dict], csv_columns: list[str]) -> list[dict]:
    """
    Validate mapping entries and return a list of warning dicts.

    Args:
        mappings:    List of mapping dicts (see build_payload()).
        csv_columns: List of column names present in the uploaded CSV.

    Returns:
        List of issue dicts, each with keys:
            entry_id (str) – affected entry
            issue    (str) – description of the problem
    """
    issues: list[dict] = []
    seen_entry_ids: set[str] = set()

    for i, mapping in enumerate(mappings):
        entry_id = mapping.get("entry_id", "").strip()
        mode = mapping.get("mode", "")
        value = mapping.get("value", "")

        label = entry_id if entry_id else f"Mapping #{i + 1}"

        # Missing entry_id
        if not entry_id:
            issues.append({"entry_id": label, "issue": "Entry ID must not be empty."})
            continue

        # Duplicate entry_id
        normalised = _normalise_entry_id(entry_id)
        if normalised in seen_entry_ids:
            issues.append(
                {"entry_id": label, "issue": f"Duplicate Entry ID: {normalised}"}
            )
        seen_entry_ids.add(normalised)

        # Validate entry_id format (must be "entry." followed by digits)
        bare = normalised.replace("entry.", "", 1)
        if not bare.isdigit():
            issues.append(
                {
                    "entry_id": label,
                    "issue": (
                        f"Invalid Entry ID format: '{entry_id}'. "
                        f"Must be 'entry.<number>'."
                    ),
                }
            )

        # CSV column must exist in the DataFrame
        if mode == MODE_CSV:
            if not value:
                issues.append({"entry_id": label, "issue": "No CSV column selected."})
            elif csv_columns and value not in csv_columns:
                issues.append(
                    {
                        "entry_id": label,
                        "issue": f"Column '{value}' not found in the uploaded CSV.",
                    }
                )

        # Static value should not be empty (warning only)
        if mode == MODE_STATIC and not value:
            issues.append(
                {
                    "entry_id": label,
                    "issue": "Static value is empty. This field will be submitted as an empty string.",
                }
            )

        # Generator must be a valid name
        if mode == MODE_GENERATOR and not value:
            issues.append({"entry_id": label, "issue": "No generator selected."})

    return issues


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def normalise_form_url(url: str) -> str:
    """
    Ensure the Google Form URL ends with /formResponse.

    Handles both the /viewform and /formResponse variants.

    Args:
        url: Raw URL string entered by the user.

    Returns:
        Corrected URL string ending with /formResponse.
    """
    url = url.strip().rstrip("/")

    if url.endswith("/formResponse"):
        return url

    if url.endswith("/viewform"):
        return url.replace("/viewform", "/formResponse")

    # Append /formResponse if missing
    return url + "/formResponse"


def is_valid_form_url(url: str) -> bool:
    """
    Return True if the URL looks like a valid Google Form response endpoint.

    Args:
        url: URL string to validate.

    Returns:
        True if the URL is a valid Google Form /formResponse endpoint.
    """
    return url.startswith("https://docs.google.com/forms/") and "formResponse" in url


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise_entry_id(entry_id: str) -> str:
    """
    Ensure the entry ID has the ``entry.`` prefix.

    Args:
        entry_id: Raw entry ID string (e.g. ``'976363616'`` or ``'entry.976363616'``).

    Returns:
        Normalised string, e.g. ``'entry.976363616'``.
    """
    entry_id = entry_id.strip()
    if not entry_id.startswith("entry."):
        return f"entry.{entry_id}"
    return entry_id


def _dict_to_series(row: dict):
    """
    Convert a plain dict to a pandas Series so that get_cell_value()
    can use pd.isna() checks correctly.

    Args:
        row: Plain dict representing one CSV row.

    Returns:
        pandas.Series wrapping the row dict.
    """
    # Import here to keep the dependency localised
    import pandas as pd  # noqa: PLC0415

    return pd.Series(row)


def _now_str() -> str:
    """Return the current time formatted as HH:MM:SS."""
    return datetime.now().strftime("%H:%M:%S")


def _log(callback, message: str) -> None:
    """
    Emit a log message via the provided callback, or no-op if None.

    Args:
        callback: Callable that accepts a single string, or None.
        message:  Message string to emit.
    """
    if callable(callback):
        try:
            callback(message)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Payload decoder
# ---------------------------------------------------------------------------

# Keys produced by Google Form itself — separated from user-data fields.
_GOOGLE_INTERNAL_KEYS = frozenset(
    {
        "dlut",
        "fbzx",
        "submissionTimestamp",
        "hud",
        "partialResponse",
        "draftResponse",
        "pageHistory",
        "fvv",
    }
)


def decode_raw_payload(raw: str) -> dict:
    """
    Parse a raw URL-encoded Google Form payload string into structured data.

    Handles:
    - ``entry.XXXX=value``        → user-data fields
    - ``entry.XXXX_sentinel=``    → sentinel marker for that entry
    - ``fvv=1``                   → form version flag
    - ``pageHistory=0,1,2``       → page-navigation history
    - All other keys              → stored as ``metadata`` or ``google_internal``

    Args:
        raw: Raw URL-encoded query string captured from a browser network
             inspector. May contain ``%XX`` percent-encoded characters.

    Returns:
        dict with keys:

        ``entries`` (list[dict])
            One dict per ``entry.*`` field (excluding sentinels)::

                {
                    "entry_id" : "entry.976363616",
                    "value"    : "Some Value",
                    "sentinel" : True,
                }

        ``fvv`` (str)
            Extracted ``fvv`` value, defaults to ``"1"``.

        ``page_history`` (str)
            Extracted ``pageHistory`` value, defaults to ``"0"``.

        ``metadata`` (dict[str, str])
            Non-entry, non-Google-internal keys.

        ``google_internal`` (dict[str, str])
            Google-generated keys: ``dlut``, ``fbzx``, ``submissionTimestamp``,
            ``hud``, ``partialResponse``, etc.

        ``sentinel_ids`` (list[str])
            Normalised entry IDs that have a corresponding ``_sentinel`` key.

        ``total_entries`` (int)
            Number of ``entry.*`` fields found (excluding sentinels).

        ``raw_pairs`` (list[tuple])
            All key/value pairs in original order (after URL-decoding).
    """
    from urllib.parse import parse_qsl, unquote
    import json

    raw = raw.strip()
    if not raw:
        return {
            "entries": [],
            "fvv": "1",
            "page_history": "0",
            "metadata": {},
            "google_internal": {},
            "sentinel_ids": [],
            "total_entries": 0,
            "raw_pairs": [],
        }

    pairs: list[tuple[str, str]] = parse_qsl(raw, keep_blank_values=True)

    entry_values: dict[str, str] = {}
    sentinel_ids: set[str] = set()
    fvv = "1"
    page_history = "0"
    metadata: dict[str, str] = {}
    google_internal: dict[str, str] = {}

    for key, value in pairs:
        # Sentinel field: entry.XXXX_sentinel
        if key.startswith("entry.") and key.endswith("_sentinel"):
            pure_id = key[: -len("_sentinel")]
            sentinel_ids.add(pure_id)

        # Regular entry field: entry.XXXX
        elif key.startswith("entry."):
            entry_values[key] = value

        # Google Form metadata
        elif key == "fvv":
            fvv = value
        elif key == "pageHistory":
            page_history = value
        elif key in _GOOGLE_INTERNAL_KEYS:
            google_internal[key] = value

        # Everything else
        else:
            metadata[key] = value

    partial_response_raw = google_internal.get("partialResponse")
    if partial_response_raw:
        try:
            parsed_partial = json.loads(unquote(partial_response_raw))
            if isinstance(parsed_partial, list) and len(parsed_partial) > 0:
                inner_list = parsed_partial[0]
                if isinstance(inner_list, list):
                    for item in inner_list:
                        if isinstance(item, list) and len(item) >= 3:
                            entry_number = item[1]
                            value_list = item[2]
                            
                            if entry_number and isinstance(value_list, list) and len(value_list) > 0:
                                entry_id = f"entry.{entry_number}"
                                val = value_list[0]
                                
                                if entry_id not in entry_values:
                                    entry_values[entry_id] = str(val)
        except Exception:
            pass

    entries: list[dict] = [
        {
            "entry_id": eid,
            "value": val,
            "sentinel": eid in sentinel_ids,
        }
        for eid, val in entry_values.items()
    ]

    return {
        "entries": entries,
        "fvv": fvv,
        "page_history": page_history,
        "metadata": metadata,
        "google_internal": google_internal,
        "sentinel_ids": sorted(sentinel_ids),
        "total_entries": len(entries),
        "raw_pairs": pairs,
    }
