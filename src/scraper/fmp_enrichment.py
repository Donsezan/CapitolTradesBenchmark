"""
Builds a party/chamber lookup from the unitedstates/congress-legislators dataset.
Source: https://unitedstates.github.io/congress-legislators/legislators-current.json
Free, no API key, updated each new Congress, includes all name variants.
"""

import logging
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

LEGISLATORS_URL = (
    "https://unitedstates.github.io/congress-legislators/legislators-current.json"
)

_PARTY_NORM = {
    "republican": "R",
    "democrat": "D",
    "democratic": "D",
    "independent": "I",
}

# Honorific words that appear in PTR XML names but not in legislator databases
_TITLE_WORDS = {"mr", "mrs", "ms", "dr", "hon", "jr", "sr", "ii", "iii", "iv"}


def _normalize_party(raw: str) -> str:
    return _PARTY_NORM.get(raw.strip().lower(), "I")


def _strip_titles(name: str) -> str:
    """'Marjorie Taylor Mrs Greene' → 'Marjorie Taylor Greene'"""
    return " ".join(w for w in name.split() if w.lower() not in _TITLE_WORDS)


def _fetch_current_legislators() -> Tuple[List[dict], Optional[str]]:
    """Fetch current Congress members. Returns (members, error_message)."""
    try:
        resp = requests.get(LEGISLATORS_URL, timeout=30)
        resp.raise_for_status()
        members = resp.json()
        logger.info("congress-legislators: fetched %d members", len(members))
        return members, None
    except Exception as exc:
        err = f"congress-legislators fetch failed: {exc}"
        logger.error(err)
        return [], err


class LegislatorLookup:
    def __init__(self, members: List[dict]):
        # "First Last" → (party, chamber)
        self.exact: Dict[str, Tuple[str, str]] = {}
        # last_name_lower → [(first_lower, party, chamber)]
        self.by_last: Dict[str, List[Tuple[str, str, str]]] = {}

        for m in members:
            terms = m.get("terms") or []
            if not terms:
                continue
            last_term = terms[-1]
            party = _normalize_party(last_term.get("party", ""))
            term_type = last_term.get("type", "rep")
            chamber = "Senate" if term_type == "sen" else "House"

            name_block = m.get("name", {})
            first = (name_block.get("first") or "").strip()
            last = (name_block.get("last") or "").strip()
            official = (name_block.get("official_full") or "").strip()
            nickname = (name_block.get("nickname") or "").strip()

            if not last:
                continue

            # Index all name variants so PTR name formats have the best chance of matching
            for full in {
                f"{first} {last}",
                official,
                f"{nickname} {last}" if nickname else None,
            }:
                if full:
                    self.exact[full] = (party, chamber)

            # last-name index (supports compound surnames like "McClain Delaney")
            self.by_last.setdefault(last.lower(), []).append(
                (first.lower(), party, chamber)
            )

    def get(self, db_name: str) -> Optional[Tuple[str, str]]:
        # 1. Direct exact match
        if db_name in self.exact:
            return self.exact[db_name]

        # 2. Strip embedded honorifics then try exact
        clean = _strip_titles(db_name)
        if clean in self.exact:
            return self.exact[clean]

        # 3. Last-name lookup — try last word, then last two words (compound surnames)
        parts = clean.split()
        last_variants = [parts[-1].lower()] if parts else []
        if len(parts) >= 3:
            last_variants.append(" ".join(parts[-2:]).lower())

        for last_key in last_variants:
            candidates = self.by_last.get(last_key, [])
            if len(candidates) == 1:
                return candidates[0][1], candidates[0][2]
            if candidates:
                first = parts[0].lower() if parts else ""
                for cand_first, cand_party, cand_chamber in candidates:
                    if cand_first.startswith(first) or first.startswith(cand_first):
                        return cand_party, cand_chamber

        return None


def build_lookup() -> Tuple[Optional[LegislatorLookup], Optional[str]]:
    """Returns (lookup, error_message). error_message is None on success."""
    members, err = _fetch_current_legislators()
    if not members:
        return None, err or "No members returned"
    return LegislatorLookup(members), None
