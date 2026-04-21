"""
Probe Finnhub congressional-trading API to determine historical data depth.

Usage:
    python scripts/probe_finnhub_depth.py

Reports:
  - Total trades returned per probe window
  - Earliest transactionDate found
  - Politicians with the most historical data
  - Whether data exists before 2020, 2018, 2016
"""

import os
import sys
from datetime import date, timedelta
from collections import Counter, defaultdict

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FINNHUB_API_KEY")
if not API_KEY:
    sys.exit("FINNHUB_API_KEY not set in .env")

BASE_URL = "https://finnhub.io/api/v1/congressional-trading"
SESSION = requests.Session()
SESSION.headers["X-Finnhub-Token"] = API_KEY


def fetch(from_date: date, to_date: date) -> list[dict]:
    params = {"from": from_date.isoformat(), "to": to_date.isoformat()}
    resp = SESSION.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def probe_window(label: str, from_date: date, to_date: date) -> list[dict]:
    trades = fetch(from_date, to_date)
    print(f"  {label:30s}  {len(trades):>5} trades")
    return trades


def main():
    today = date.today()
    all_trades: list[dict] = []

    print("=== Finnhub Data Depth Probe ===\n")
    print("Probing recent windows to confirm API is live:")
    for label, days_back in [("Last 30 days", 30), ("Last 90 days", 90), ("Last 180 days", 180)]:
        trades = probe_window(label, today - timedelta(days=days_back), today)
        all_trades.extend(trades)

    print("\nProbing historical years (Jan 1 – Dec 31):")
    yearly: dict[int, list[dict]] = {}
    for year in range(today.year, 2011, -1):
        start = date(year, 1, 1)
        end = min(date(year, 12, 31), today)
        trades = probe_window(str(year), start, end)
        yearly[year] = trades
        all_trades.extend(trades)
        # Stop probing if two consecutive years are empty
        recent_years = [yearly.get(y, []) for y in range(year, min(year + 2, today.year + 1))]
        if year < today.year - 1 and all(len(t) == 0 for t in recent_years):
            print(f"  (stopping — two consecutive empty years at {year})")
            break

    # Deduplicate by a rough key
    seen: set[str] = set()
    unique: list[dict] = []
    for t in all_trades:
        key = f"{t.get('name')}|{t.get('symbol')}|{t.get('transactionDate')}|{t.get('transactionType')}"
        if key not in seen:
            seen.add(key)
            unique.append(t)

    if not unique:
        print("\nNo trades found — check your API key or Finnhub plan.")
        return

    dates = [d for t in unique if (d := t.get("transactionDate"))]
    dates.sort()

    print(f"\n=== Summary ===")
    print(f"Total unique trades found:  {len(unique)}")
    print(f"Earliest transactionDate:   {dates[0] if dates else 'N/A'}")
    print(f"Latest  transactionDate:    {dates[-1] if dates else 'N/A'}")

    print("\nData availability by milestone year:")
    for cutoff in [2024, 2022, 2020, 2018, 2016, 2014, 2012]:
        count = sum(1 for d in dates if d.startswith(str(cutoff)[:4]) or d < f"{cutoff + 1}-01-01")
        has_data = any(d < f"{cutoff + 1}-01-01" for d in dates)
        marker = "YES" if has_data else " NO"
        print(f"  Data before {cutoff + 1}-01-01:  {marker}")

    print("\nTop 10 politicians by trade count:")
    name_counts: Counter = Counter(t.get("name", "Unknown") for t in unique)
    for name, count in name_counts.most_common(10):
        earliest = min(
            (t.get("transactionDate", "9999") for t in unique if t.get("name") == name),
            default="N/A"
        )
        print(f"  {name:35s}  {count:>4} trades  (earliest: {earliest})")

    print("\nTrade count by year:")
    year_counts: Counter = Counter(d[:4] for d in dates)
    for year in sorted(year_counts):
        bar = "█" * (year_counts[year] // 10)
        print(f"  {year}  {year_counts[year]:>5}  {bar}")


if __name__ == "__main__":
    main()
