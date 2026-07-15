from datetime import datetime
import os
import re


def sort_paths_chronologically(paths):
    return sorted(paths, key=extract_datetime)

def extract_datetime(path):
    DATE_RE = re.compile(
        r"([a-z]+-\d{1,2}-\d{4}-\d{1,2}(?:am|pm))",
        re.IGNORECASE,
    )
    filename = os.path.basename(path)
    match = DATE_RE.search(filename)
    if not match:
        raise ValueError(f"Could not find timestamp in: {path}")
    
    return datetime.strptime(match.group(1), "%B-%d-%Y-%I%p")

