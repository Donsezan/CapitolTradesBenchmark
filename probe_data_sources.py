"""
Probe script: verifies the Quiverquant congressional trading API and summarises
what data is available for free (no auth).

Results (2026-04-18):
  - Finnhub /congressional-trading  → PREMIUM ONLY (returns HTML on free key)
  - Quiverquant /live/congresstrading → FREE, ~1000 most recent records (~1 year)
  - capitoltrades.com BFF API        → BLOCKED by CloudFront for direct access
  - Historical (5Y+) from QQ         → requires API token (free account at quiverquant.com)

Run: python probe_data_sources.py
"""

import os
import requests
from datetime import date
from collections import defaultdict

API_KEY = os.getenv("QUIVERQUANT_API_KEY")  # optional — free endpoint works without it
BASE_URL = "https://api.quiverquant.com/beta/live/congresstrading"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}
if API_KEY:
    HEADERS["Authorization"] = f"Token {API_KEY}"


def main():
    print("=" * 60)
    print("  Quiverquant Congressional Trading — Data Probe")
    print("=" * 60)

    print("\n[1] Fetching all available records...")
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    records = resp.json()

    if not records:
        print("  WARNING: No records returned. Check API status.")
        return

    print(f"  Total records : {len(records)}")

    dates = sorted(r["TransactionDate"] for r in records if r.get("TransactionDate"))
    print(f"  Earliest date : {dates[0]}")
    print(f"  Latest date   : {dates[-1]}")

    politicians: dict[str, int] = defaultdict(int)
    tickers: dict[str, int] = defaultdict(int)
    tx_types: dict[str, int] = defaultdict(int)
    parties: dict[str, int] = defaultdict(int)
    chambers: dict[str, int] = defaultdict(int)

    for r in records:
        politicians[r.get("Representative", "Unknown")] += 1
        tickers[r.get("Ticker", "?")] += 1
        tx_types[r.get("Transaction", "?")] += 1
        parties[r.get("Party", "?")] += 1
        chambers[r.get("House", "?")] += 1

    print(f"\n[2] Top 10 politicians by trade count:")
    for name, cnt in sorted(politicians.items(), key=lambda x: -x[1])[:10]:
        print(f"  {cnt:>4}  {name}")

    print(f"\n[3] Top 10 tickers:")
    for ticker, cnt in sorted(tickers.items(), key=lambda x: -x[1])[:10]:
        print(f"  {cnt:>4}  {ticker}")

    print(f"\n[4] Transaction types:")
    for tx, cnt in sorted(tx_types.items(), key=lambda x: -x[1]):
        print(f"  {cnt:>4}  {tx}")

    print(f"\n[5] Parties:")
    for party, cnt in sorted(parties.items(), key=lambda x: -x[1]):
        print(f"  {cnt:>4}  {party}")

    print(f"\n[6] Chambers:")
    for chamber, cnt in sorted(chambers.items(), key=lambda x: -x[1]):
        print(f"  {cnt:>4}  {chamber}")

    print(f"\n[7] Available fields:")
    print(f"  {list(records[0].keys())}")

    print("\n" + "=" * 60)
    print("  CONCLUSION")
    print("=" * 60)
    print(f"  Free tier covers: {dates[0]} → {dates[-1]}")
    print(f"  Supports ranges:  1D, 5D, 1M, 6M, 1Y")
    print(f"  For 5Y / MAX:     set QUIVERQUANT_API_KEY in .env")
    print("=" * 60)


if __name__ == "__main__":
    main()
