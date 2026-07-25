import gzip
import json
from pathlib import Path
import gzip
import time
import urllib.request


DATASETS_DIR = Path("datasets")

def get_current_market_names(full_name):
    
    #print(f"Fetching market metadata for {market} at {time_name}")
    path = f"https://gamma-api.polymarket.com/events?slug={full_name}"
    #print(path)
    request = urllib.request.Request(
        path,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://polymarket.com/",
        },
    )
    try: 
        with urllib.request.urlopen(request, timeout=20) as url:
            market_metadata = json.loads(url.read().decode())
    except Exception as e:
        print(f"Error fetching market metadata for {full_name}: {e}")
        market_metadata = None
    return market_metadata

def has_required_metadata(metadata_end):
    """
    Returns True if metadata_end contains:
    metadata_end[0]["eventMetadata"]["finalPrice"]
    metadata_end[0]["eventMetadata"]["priceToBeat"]
    """
    try:
        event_metadata = metadata_end[0]["eventMetadata"]
        return (
            "finalPrice" in event_metadata
            and "priceToBeat" in event_metadata
        )
    except (IndexError, KeyError, TypeError):
        return False


for gz_file in DATASETS_DIR.rglob("*.gz"):
    print(f"Checking {gz_file}")
    newer_than_time = 5 * 24 * 60 * 60  # 5 days in seconds
    file_creation_date = gz_file.stat().st_ctime
    if file_creation_date < time.time() - newer_than_time:
        #print(f"  Skipping {gz_file} (too old)")
        continue
    try:
        with gzip.open(gz_file, "rt", encoding="utf-8") as f:
            data = json.load(f)

        if not has_required_metadata(data.get("metadata_end")):
            market_name = gz_file.stem  # filename without .gz

            print(f"  Updating metadata_end for {market_name}")

            data["metadata_end"] = get_current_market_names(market_name)
            
            if has_required_metadata(data.get("metadata_end")):
                #print(data["metadata_end"])
                with gzip.open(gz_file, "wt", encoding="utf-8") as f:
                    json.dump(data, f, separators=(",", ":"))
            else:
                print(f"  Warning: metadata_end for {market_name} still missing required fields after update.")

    except Exception as e:
        print(f"Failed to process {gz_file}: {e}")