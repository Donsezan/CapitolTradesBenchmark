"""
Probe disclosures-clerk.house.gov to determine how far back PTR data goes.

Usage:
    python scripts/probe_house_depth.py

Reports:
  - Filing counts per year
  - Earliest year with data available
"""

import io
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; CapitolTradeFollower/1.0)"
BASE_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs"


def probe_year(year: int) -> int:
    url = f"{BASE_URL}/{year}FD.zip"
    try:
        resp = SESSION.get(url, timeout=30)
        if resp.status_code == 404:
            return -1  # year not available
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  {year}  ERROR: {exc}")
        return -1

    ptr_count = 0
    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            with z.open(f"{year}FD.xml") as f:
                root = ET.parse(f).getroot()
                for member in root:
                    if member.findtext("FilingType") == "P":
                        ptr_count += 1
    except Exception as exc:
        print(f"  {year}  PARSE ERROR: {exc}")
        return -1

    return ptr_count


def main():
    print("=== House PTR Data Depth Probe ===")
    print(f"Source: {BASE_URL}/<year>FD.zip\n")
    print(f"{'Year':<6}  {'PTR Filings':>12}  Notes")
    print("-" * 40)

    today_year = datetime.today().year
    earliest_with_data = None

    for year in range(today_year, 2009, -1):
        count = probe_year(year)
        if count == -1:
            print(f"  {year}   not available")
            # Two consecutive misses → stop
            if earliest_with_data and year < earliest_with_data - 2:
                break
            continue
        label = " <- earliest" if (earliest_with_data is None or year < earliest_with_data) else ""
        print(f"  {year}   {count:>8} PTR filings{label}")
        earliest_with_data = year

    print()
    if earliest_with_data:
        print(f"Earliest year with PTR data:  {earliest_with_data}")
        print(f"Range available:              {earliest_with_data}–{today_year}")
        print(f"\nNote: These are House filings only.")
        print(f"Senate data is at efts.senate.gov (separate scraper needed).")
    else:
        print("No data found — check network connectivity.")


if __name__ == "__main__":
    main()
