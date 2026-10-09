"""Shared harvest scoring; weights and venue recognition are unchanged."""

import math
import re

RECOGNIZED_VENUES = re.compile(
    r"ICSE|ESEC|FSE|\bASE\b|ISSTA|ICSME|MSR\b|SANER|TOSEM|TSE\b"
    r"|Empirical Software Engineering|IEEE Software|CACM"
    r"|Communications of the ACM|CHI\b|CSCW|UIST|IUI\b|TOCHI"
    r"|NeurIPS|Neural Information Processing|ICLR|ICML|AAAI"
    r"|\bACL\b|EMNLP|NAACL|Requirements Engineering",
    re.IGNORECASE,
)


def quality_gate(p: dict, this_year: int) -> bool:
    """Good-quality only: verifiable, titled, and either fresh or cited."""
    ext = p.get("externalIds") or {}
    if not (ext.get("ArXiv") or ext.get("DOI")):
        return False
    year, cites = p.get("year"), p.get("citationCount") or 0
    if not p.get("title") or not year:
        return False
    if year < 2015 and cites < 200:
        return False
    if year < 2018 and cites < 100:
        return False
    if year <= this_year - 3 and cites < 10:
        return False
    if year == this_year - 2 and cites < 3:  # noqa: SIM103 - guard ladder
        return False
    return True


def is_recognized_venue(p: dict) -> bool:
    return bool(RECOGNIZED_VENUES.search((p.get("venue") or "").strip()))


def score(p: dict, edges: int, this_year: int) -> float:
    year = p.get("year") or 0
    cites = p.get("citationCount") or 0
    infl = p.get("influentialCitationCount") or 0
    freshness = max(0, 5 - (this_year - year)) * 1.6
    impact = math.log10(cites + 1) * 2.0
    influence = math.log10(infl + 1) * 1.2
    connectivity = min(edges, 6) * 1.5
    venue = 0.5 if (p.get("venue") or "").strip() else 0.0
    venue += 1.0 if is_recognized_venue(p) else 0.0
    open_access = 0.4 if p.get("openAccessPdf") else 0.0
    return round(freshness + impact + influence + connectivity + venue + open_access, 3)


def candidate_score(candidate: dict, this_year: int) -> float:
    """Rank a refresh candidate with the harvest formula; it has no graph edges yet."""
    paper = {
        "year": candidate.get("year"),
        "citationCount": candidate.get("citationCount"),
        "influentialCitationCount": None,
        "venue": candidate.get("venue") or "",
        # arXiv papers are open access by construction.
        "openAccessPdf": bool(candidate.get("arxivId")) or None,
    }
    return score(paper, edges=0, this_year=this_year)
