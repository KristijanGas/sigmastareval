from datetime import datetime
import os
import re


def sort_paths_chronologically(paths):
    return sorted(paths, key=extract_datetime)

def extract_datetime(path):
    UNIX_TIMESTAMP_RE = re.compile(r"-(\d{10})(?=\.gz$)")
    READABLE_DATE_RE = re.compile(
        r"([a-z]+-\d{1,2}-\d{4}-\d{1,2}(?:am|pm))",
        re.IGNORECASE,
    )
    filename = os.path.basename(path)
    readable_match = READABLE_DATE_RE.search(filename)
    if readable_match:
        parsed = datetime.strptime(
            readable_match.group(1),
            "%B-%d-%Y-%I%p",
        )
        return parsed.timestamp()
    

    unix_match = UNIX_TIMESTAMP_RE.search(filename)
    if unix_match:
        return int(unix_match.group(1))
    
    raise ValueError(f"Could not find a supported timestamp in: {path}")

from datetime import datetime
import re

def extract_timestamp(filename: str) -> int:
    """
    Extracts the Unix timestamp from filenames like:
      bitcoin-up-or-down-july-9-2026-4am-et.gz
      ethereum-up-or-down-july-9-2026-4pm-et.gz
      bitcoin-cash-up-or-down-december-31-2027-11pm-et.gz

    Returns:
        Unix timestamp (seconds).
    Raises:
        ValueError if no valid date is found.
    """
    pattern = re.compile(
        r"(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)-"
        r"(\d{1,2})-"
        r"(\d{4})-"
        r"(\d{1,2})(am|pm)-et",
        re.IGNORECASE,
    )

    match = pattern.search(filename)
    if not match:
        raise ValueError(f"Could not extract date from: {filename}")

    month, day, year, hour, am_pm = match.groups()

    dt = datetime.strptime(
        f"{month} {day} {year} {hour}{am_pm}",
        "%B %d %Y %I%p",
    )

    return int(dt.timestamp())

