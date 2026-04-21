"""
Scrapes U.S. House STOCK Act Periodic Transaction Reports (PTRs) from
disclosures-clerk.house.gov — the official free source of congressional trade data.
"""

import asyncio
import io
import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import List, Optional, Tuple

import pdfplumber
import requests

from src.models.trade import Trade

logger = logging.getLogger(__name__)

BASE_URL = "https://disclosures-clerk.house.gov"

_TX_MAP = {
    "p": "BUY",
    "s": "SELL",
    "s (partial)": "SELL",
    "s (full)": "SELL",
    "s (partial sale)": "SELL",
}

_DATE_RE = re.compile(r"\d{2}/\d{2}/\d{4}")
_TICKER_RE = re.compile(r"\(([A-Z]{1,5})\)")
_AMOUNT_RE = re.compile(r"\$([0-9,]+)")
_TX_TYPE_RE = re.compile(
    r"\b(P|S(?:\s+\((?:partial|full)(?:\s+sale)?\))?)\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)


def _parse_amount(s: str) -> float:
    return float(s.replace(",", ""))


class HouseScraper:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (compatible; CapitolTradeFollower/1.0)"
        )

    # ── Index ────────────────────────────────────────────────────────────────

    def fetch_ptr_index(self, year: int) -> List[Tuple[str, int, date]]:
        """Return (politician_name, doc_id, filing_date) for all PTR filings in year."""
        url = f"{BASE_URL}/public_disc/financial-pdfs/{year}FD.zip"
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()

        records: List[Tuple[str, int, date]] = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            with z.open(f"{year}FD.xml") as f:
                root = ET.parse(f).getroot()
                for member in root:
                    if member.findtext("FilingType") != "P":
                        continue
                    first = member.findtext("First") or ""
                    last = member.findtext("Last") or ""
                    name = f"{first} {last}".strip()
                    doc_id_str = member.findtext("DocID") or ""
                    date_str = member.findtext("FilingDate") or ""
                    try:
                        doc_id = int(doc_id_str)
                        filing_date = datetime.strptime(date_str, "%m/%d/%Y").date()
                    except (ValueError, TypeError):
                        continue
                    records.append((name, doc_id, filing_date))

        logger.info("PTR index for %d: %d filings", year, len(records))
        return records

    # ── PDF fetch & parse ────────────────────────────────────────────────────

    def fetch_ptr_text(self, doc_id: int, year: int) -> Optional[str]:
        """Download PTR PDF and return concatenated page text, or None if not found."""
        url = f"{BASE_URL}/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
        resp = self._session.get(url, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        pages: List[str] = []
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
        return "\n".join(pages)

    def parse_ptr_text(
        self,
        text: str,
        politician_name: str,
        politician_id: int = 0,
        party: str = "I",
        chamber: str = "House",
    ) -> List[Trade]:
        """Parse PTR page text into a list of Trade objects."""
        text = self._join_amount_continuations(text)
        trades: List[Trade] = []
        for line in text.splitlines():
            trade = self._parse_line(line, politician_name, politician_id, party, chamber)
            if trade:
                trades.append(trade)
        return trades

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _join_amount_continuations(self, text: str) -> str:
        """
        PTR PDFs split each trade across two lines:
          line N:   "... (TICK) P 01/15/2024 01/15/2024  $250,001 -"
          line N+1: "[ST] $500,000"  /  "(TICK) [OP] $500,000"  /  "Stock (NVDA) [ST] $5,000,000"
        Join them so each trade is on one line for regex matching.
        """
        lines = text.splitlines()
        result: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.rstrip().endswith("-") and i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                # Continuation if next line has a $ amount (covers all wrapping variants)
                if _AMOUNT_RE.search(nxt):
                    result.append(line.rstrip() + " " + nxt)
                    i += 2
                    continue
            result.append(line)
            i += 1
        return "\n".join(result)

    def _parse_line(
        self,
        line: str,
        politician_name: str,
        politician_id: int,
        party: str,
        chamber: str,
    ) -> Optional[Trade]:
        dates = _DATE_RE.findall(line)
        if len(dates) < 2:
            return None

        tx_match = _TX_TYPE_RE.search(line)
        if not tx_match:
            return None

        tx_raw = tx_match.group(1).strip().lower()
        trade_type = _TX_MAP.get(tx_raw)
        if not trade_type:
            return None

        try:
            trade_date = datetime.strptime(dates[0], "%m/%d/%Y").date()
            filing_date = datetime.strptime(dates[1], "%m/%d/%Y").date()
        except ValueError:
            return None

        # Prefer ticker appearing before the transaction type anchor
        pre = line[: tx_match.start()]
        tickers = _TICKER_RE.findall(pre) or _TICKER_RE.findall(line)
        if not tickers:
            return None
        ticker = tickers[-1]

        amounts = [_parse_amount(a) for a in _AMOUNT_RE.findall(line)]
        if len(amounts) < 2:
            return None
        amount_from = min(amounts[-2], amounts[-1])
        amount_to = max(amounts[-2], amounts[-1])

        return Trade(
            politician_id=politician_id,
            politician_name=politician_name,
            ticker=ticker,
            trade_type=trade_type,
            amount_from=amount_from,
            amount_to=amount_to,
            trade_date=trade_date,
            filing_date=filing_date,
            party=party,
            chamber=chamber,
        )

    # ── Async entry point ────────────────────────────────────────────────────

    async def fetch_trades(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        max_pdfs: int = 200,
    ) -> List[Tuple[str, int, List[Trade]]]:
        """
        Fetch and parse PTR filings whose filing_date falls within [from_date, to_date].
        Returns list of (politician_name, doc_id, trades).
        """
        if from_date is None:
            from_date = date.today().replace(month=1, day=1)
        if to_date is None:
            to_date = date.today()

        years = sorted({from_date.year, to_date.year})
        loop = asyncio.get_running_loop()

        all_ptrs: List[Tuple[str, int, date, int]] = []
        for year in years:
            try:
                index = await loop.run_in_executor(
                    None, lambda y=year: self.fetch_ptr_index(y)
                )
                for name, doc_id, filing_date in index:
                    all_ptrs.append((name, doc_id, filing_date, year))
            except Exception as exc:
                logger.error("PTR index fetch failed for %d: %s", year, exc)

        in_range = [
            (name, doc_id, filing_date, year)
            for name, doc_id, filing_date, year in all_ptrs
            if from_date <= filing_date <= to_date
        ]
        in_range.sort(key=lambda x: x[2], reverse=True)

        logger.info(
            "House PTR: %d filings in %s–%s, processing up to %d",
            len(in_range), from_date, to_date, max_pdfs,
        )

        results: List[Tuple[str, int, List[Trade]]] = []
        for name, doc_id, filing_date, year in in_range[:max_pdfs]:
            try:
                # Each lambda captures d/y by default-arg to avoid late-binding closure bug.
                text = await loop.run_in_executor(
                    None, lambda d=doc_id, y=year: self.fetch_ptr_text(d, y)
                )
                if text is None:
                    continue
                trades = self.parse_ptr_text(text, politician_name=name)
                if trades:
                    results.append((name, doc_id, trades))
                    logger.debug("DocID=%d %s → %d trades", doc_id, name, len(trades))
            except Exception as exc:
                logger.warning("Failed DocID=%d (%s): %s", doc_id, name, exc)

        total = sum(len(t) for _, _, t in results)
        logger.info("House PTR scrape complete: %d PDFs, %d trades", len(results), total)
        return results
