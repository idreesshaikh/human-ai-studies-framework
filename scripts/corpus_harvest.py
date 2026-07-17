"""Corpus harvest pipeline (FR-LIT-8): grow the paper corpus by citation
snowballing from the hand-curated seed set.

Tier A = the 58 hand-curated seeds in docs/papers/README.md (never touched).
Tier B = harvested candidates: every reference and citation of every seed,
fetched from the Semantic Scholar Graph API (D8), quality-filtered,
recency-weighted, connectivity-ranked, deduplicated.

Honesty rules (the corpus's whole value is that it is real):
- Only papers returned by the live API enter the index - nothing is ever
  synthesized. Seeds that the API cannot resolve are reported, not faked.
- Every Tier B row records which seeds discovered it (`via`), its S2
  paperId, and its external IDs, so every entry is independently
  verifiable.

Usage:  uv run python scripts/corpus_harvest.py [--target 1000]
Resumable: per-seed API responses are cached in --cache-dir; rerunning
skips fetched seeds and re-ranks. Emits docs/papers/corpus-index.json
(machine layer, consumed by the platform importer) and docs/papers/CORPUS.md
(generated human index). Stdlib only (zero-bloat, D8 posture); paced to
the public rate limit with exponential backoff on 429.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

API = "https://api.semanticscholar.org/graph/v1/paper/"
NESTED_FIELDS = ",".join(
    f"{side}.{f}"
    for side in ("references", "citations")
    for f in ("paperId", "title", "year", "externalIds", "citationCount", "venue")
)
REPO = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO / "docs" / "papers"
PAUSE_S = 1.2  # public-pool pacing (D8: self-paced, never hammer)
MAX_BACKOFF_S = 120


def log(msg: str) -> None:
    print(f"[harvest] {msg}", flush=True)


def read_seeds() -> list[str]:
    text = (PAPERS_DIR / "README.md").read_text()
    ids = re.findall(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})", text)
    seen: dict[str, None] = {}
    for i in ids:
        seen.setdefault(i, None)
    return list(seen)


def fetch_seed(arxiv_id: str, cache_dir: Path) -> dict | None:
    cache = cache_dir / f"{arxiv_id}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    url = f"{API}arXiv:{arxiv_id}?fields=title,year,{NESTED_FIELDS}"
    backoff = PAUSE_S
    for _ in range(8):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read())
                cache.write_text(json.dumps(data))
                time.sleep(PAUSE_S)
                return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                cache.write_text("null")
                time.sleep(PAUSE_S)
                return None
            if e.code == 429:
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF_S)
                continue
            log(f"  {arxiv_id}: HTTP {e.code}, skipping")
            return None
        except (urllib.error.URLError, TimeoutError):
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)
    log(f"  {arxiv_id}: gave up after retries (not cached, rerun resumes)")
    return None


def quality_gate(p: dict, this_year: int) -> bool:
    """Good-quality only: verifiable, titled, and either fresh or cited."""
    ext = p.get("externalIds") or {}
    if not (ext.get("ArXiv") or ext.get("DOI")):
        return False  # unverifiable -> out
    year, cites = p.get("year"), p.get("citationCount") or 0
    if not p.get("title") or not year:
        return False
    if year < 2015 and cites < 200:
        return False  # pre-deep-learning-era: classics only
    if year < 2018 and cites < 100:
        return False
    if year <= this_year - 3 and cites < 10:
        return False  # had years to be cited, wasn't
    if year == this_year - 2 and cites < 3:
        return False
    return True  # fresh papers (last ~2y) pass on seed-connectivity alone


def score(p: dict, edges: int, this_year: int) -> float:
    year = p.get("year") or 0
    cites = p.get("citationCount") or 0
    freshness = max(0, 5 - (this_year - year)) * 1.6  # fresh precedence
    impact = math.log10(cites + 1) * 2.0
    connectivity = min(edges, 6) * 1.5  # cited by/citing many seeds
    venue = 0.5 if (p.get("venue") or "").strip() else 0.0
    return round(freshness + impact + connectivity + venue, 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1000)
    ap.add_argument("--cache-dir", type=Path, required=True)
    args = ap.parse_args()
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    this_year = date.today().year

    seeds = read_seeds()
    log(f"{len(seeds)} seed arXiv ids from README.md")

    candidates: dict[str, dict] = {}
    edges: dict[str, set[str]] = {}
    seed_pids: set[str] = set()
    resolved = 0
    for n, sid in enumerate(seeds, 1):
        data = fetch_seed(sid, args.cache_dir)
        if not data:
            log(f"  [{n}/{len(seeds)}] arXiv:{sid} unresolved")
            continue
        resolved += 1
        if data.get("paperId"):
            seed_pids.add(data["paperId"])
        pool = (data.get("references") or []) + (data.get("citations") or [])
        for p in pool:
            pid = p.get("paperId")
            if not pid:
                continue
            edges.setdefault(pid, set()).add(sid)
            best = candidates.get(pid)
            if best is None or (p.get("citationCount") or 0) > (
                best.get("citationCount") or 0
            ):
                candidates[pid] = p
        log(f"  [{n}/{len(seeds)}] arXiv:{sid} -> +{len(pool)} mentions")

    passed = [
        (score(p, len(edges[pid]), this_year), pid, p)
        for pid, p in candidates.items()
        if pid not in seed_pids and quality_gate(p, this_year)
    ]
    passed.sort(key=lambda t: (-t[0], t[1]))
    room = args.target - len(seeds)
    picked = passed[:room]
    log(
        f"seeds resolved {resolved}/{len(seeds)}; candidates {len(candidates)}; "
        f"passed gate {len(passed)}; picked {len(picked)} (room {room})"
    )

    def ref_of(p: dict) -> str:
        ext = p.get("externalIds") or {}
        if ext.get("ArXiv"):
            return f"arxiv:{ext['ArXiv']}"
        return f"doi:{ext['DOI']}"

    index = {
        "generatedAt": date.today().isoformat(),
        "pipeline": "scripts/corpus_harvest.py (FR-LIT-8; D8/D36)",
        "tierA": {"count": len(seeds), "source": "docs/papers/README.md"},
        "tierB": [
            {
                "ref": ref_of(p),
                "s2PaperId": pid,
                "title": p["title"],
                "year": p["year"],
                "venue": (p.get("venue") or "").strip() or None,
                "citationCount": p.get("citationCount") or 0,
                "score": s,
                "via": sorted(edges[pid]),
            }
            for s, pid, p in picked
        ],
    }
    (PAPERS_DIR / "corpus-index.json").write_text(
        json.dumps(index, indent=1, ensure_ascii=False)
    )

    lines = [
        "# Corpus Tier B — harvested index (generated, do not hand-edit)",
        "",
        f"Generated {index['generatedAt']} by `scripts/corpus_harvest.py` "
        "(FR-LIT-8). Tier A = the hand-curated seeds in `README.md`. Every row "
        "below was returned by the Semantic Scholar Graph API via citation "
        "snowballing from the seeds — quality-gated, recency-weighted, "
        "connectivity-ranked. `via` = seed arXiv ids that discovered it. "
        "Verify any row at `https://api.semanticscholar.org/graph/v1/paper/"
        "<ref>`.",
        "",
        f"**{len(picked)} papers** (+ {len(seeds)} Tier A seeds = "
        f"{len(picked) + len(seeds)} total).",
        "",
        "| Ref | Title | Year | Venue | Cites | Score | Via seeds |",
        "| --- | ----- | ---- | ----- | ----- | ----- | --------- |",
    ]
    for s, pid, p in picked:
        title = p["title"].replace("|", "\\|")
        venue = ((p.get("venue") or "").strip() or "—").replace("|", "\\|")
        lines.append(
            f"| `{ref_of(p)}` | {title} | {p['year']} | {venue} | "
            f"{p.get('citationCount') or 0} | {s} | {len(edges[pid])} |"
        )
    (PAPERS_DIR / "CORPUS.md").write_text("\n".join(lines) + "\n")
    log(f"wrote corpus-index.json + CORPUS.md ({len(picked) + len(seeds)} papers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
