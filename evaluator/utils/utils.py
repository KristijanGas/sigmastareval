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

