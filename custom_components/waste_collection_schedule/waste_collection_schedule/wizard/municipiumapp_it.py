#!/usr/bin/env python3
"""Regenerate the MUNICIPALITIES list in source/municipiumapp_it.py.

Queries the Municipium cloud API for all municipalities, keeps the ones that
publish at least one waste collection calendar and rewrites the auto-generated
block in the source module.
"""

import itertools
import random
import re
import site
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

package_dir = Path(__file__).resolve().parents[2]
site.addsitedir(str(package_dir))

from waste_collection_schedule.source.municipiumapp_it import (  # noqa: E402
    CLOUD_API_URL,
    HEADERS,
)

SOURCE_FILE = (
    package_dir / "waste_collection_schedule" / "source" / "municipiumapp_it.py"
)

BEGIN_MARKER = "# --- BEGIN MUNICIPALITIES (auto-generated) ---"
END_MARKER = "# --- END MUNICIPALITIES ---"

MAX_WORKERS = 4
MAX_ATTEMPTS = 5

_progress = itertools.count(1)


def get(url: str):
    for attempt in range(MAX_ATTEMPTS):
        # Random delay to keep the request rate below the API's rate limit
        time.sleep(random.uniform(0.3, 0.8))
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = int(retry_after)
            else:
                delay = 2**attempt + random.uniform(0, 1)
            print(f"rate limited, retrying in {delay:.1f}s: {url}")
            time.sleep(delay)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"still rate limited after {MAX_ATTEMPTS} attempts: {url}")


def check_municipality(municipality: dict) -> str | None:
    """Return the municipality name if it publishes at least one calendar."""
    name = municipality["name"].strip()
    try:
        details = get(
            f"{CLOUD_API_URL}/municipalities/show_mobile/{municipality['id']}"
        )
        if not details.get("enable_garbage_calendar") or not details.get("subdomain"):
            return None
        calendars = get(f"https://{details['subdomain']}/api/v2/calendars")
        return name if calendars else None
    except Exception as e:
        print(f"skipping {name}: {e}")
        return None
    finally:
        checked = next(_progress)
        if checked % 100 == 0:
            print(f"...checked {checked} municipalities")


def main():
    municipalities = get(f"{CLOUD_API_URL}/municipalities")
    print(f"Checking {len(municipalities)} municipalities...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        names = [n for n in executor.map(check_municipality, municipalities) if n]

    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise SystemExit(
            f"Duplicate municipality names found: {sorted(duplicates)}. "
            "The MUNICIPALITIES list needs a province qualifier to disambiguate "
            "them - please update source and wizard accordingly."
        )
    if any('"' in n for n in names):
        raise SystemExit("Municipality name contains a double quote.")

    names.sort(key=str.casefold)

    block = "\n".join(
        [
            BEGIN_MARKER,
            "# Municipalities that publish at least one waste collection calendar on Municipium.",
            "# Regenerate with: python custom_components/waste_collection_schedule/waste_collection_schedule/wizard/municipiumapp_it.py",
            "MUNICIPALITIES = [",
            *(f'    "{n}",' for n in names),
            "]",
            END_MARKER,
        ]
    )

    text = SOURCE_FILE.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL
    )
    new_text, count = pattern.subn(lambda _: block, text)
    if count != 1:
        raise SystemExit(f"Expected exactly one municipalities block, found {count}.")
    SOURCE_FILE.write_text(new_text, encoding="utf-8")
    print(f"Wrote {len(names)} municipalities to {SOURCE_FILE}")


if __name__ == "__main__":
    main()
