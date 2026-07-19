"""Corpus harvest pipeline (FR-LIT-8): grow the paper corpus by citation
snowballing from the hand-curated seed set.

Tier A = the hand-curated seeds in docs/papers/README.md (never touched).
Tier B = harvested candidates: every reference and citation of every seed,
fetched from the Semantic Scholar Graph API (D8), quality-filtered,
recency-weighted, connectivity-ranked, deduplicated.

Honesty rules (the corpus's whole value is that it is real):
- Only papers returned by the live API enter the index - nothing is ever
  synthesized. Seeds that the API cannot resolve are reported, not faked.
- Every Tier B row records which seeds discovered it (`via`), its S2
  paperId, and its external IDs, so every entry is independently
  verifiable.

Usage:  uv run python scripts/corpus_harvest.py [--target 0]
The corpus is quality-first and UNCAPPED (FR-LIT-8 rev 2): with the
default --target 0, every candidate that passes the quality gate AND is
woven into the seed graph (>= MIN_EDGES_UNCAPPED seeds, or fresh) ships;
1,000 is the floor, not the ceiling. Pass --target N to reproduce the
old capped top-N behavior. --propose-tier-a N emits a promotion
shortlist from the existing index for hand-curation into Tier A.
Resumable: per-seed API responses are cached in --cache-dir; rerunning
skips fetched seeds and re-ranks. Emits docs/papers/corpus-index.json
(machine layer, consumed by the platform importer) and docs/papers/CORPUS.md
(generated human index). Stdlib only (zero-bloat, D8 posture); paced to
the public rate limit with exponential backoff on 429.

Auth: set S2_API_KEY (runtime env only - never git/CI, D32 key posture)
to use the authenticated pool: dedicated 1 req/s, no shared-pool 429s.

Verification (FR-LIT-8 fit criterion F8.1):
    uv run python scripts/corpus_harvest.py --verify
re-fetches every Tier B row from the live API (batch endpoint, 500 ids
per call) and checks stored title + external id against the live record.
Exit 0 = every row verified; exit 1 = any mismatch (printed). Unresolved
ids (papers the API no longer returns) are reported separately - they
are staleness, not fabrication, and a fresh harvest clears them.
"""

from __future__ import annotations

import argparse
import json
import math
import os
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
    for f in (
        "paperId",
        "title",
        "year",
        "externalIds",
        "citationCount",
        "influentialCitationCount",
        "venue",
        "publicationTypes",
        "openAccessPdf",
    )
)
REPO = Path(__file__).resolve().parent.parent
PAPERS_DIR = REPO / "docs" / "papers"
PAUSE_S = 1.2  # public-pool pacing (D8: self-paced, never hammer)
MAX_BACKOFF_S = 120

# Gate/rank constants are versioned editorial judgment (FR-LIT-8 honesty
# invariant: changing them is a recorded decision, not a tweak). v2 adds
# influence, venue recognition, and open-access (reproducibility proxy).
SCORING_VERSION = 2
MIN_EDGES_UNCAPPED = 2  # non-fresh papers must be woven into >=2 seeds
FRESH_WINDOW_Y = 2  # papers this recent pass on any connectivity
RECOGNIZED_VENUES = re.compile(
    r"ICSE|ESEC|FSE|\bASE\b|ISSTA|ICSME|MSR\b|SANER|TOSEM|TSE\b"
    r"|Empirical Software Engineering|IEEE Software|CACM"
    r"|Communications of the ACM|CHI\b|CSCW|UIST|IUI\b|TOCHI"
    r"|NeurIPS|Neural Information Processing|ICLR|ICML|AAAI"
    r"|\bACL\b|EMNLP|NAACL|Requirements Engineering",
    re.IGNORECASE,
)


def log(msg: str) -> None:
    print(f"[harvest] {msg}", flush=True)


def read_seeds() -> tuple[int, list[str], set[str]]:
    """Tier A row count, the arXiv ids usable for snowballing, and the
    lowercased DOIs of DOI-only seeds.

    Seeds without an arXiv id (author preprints, DOI-only promotions)
    still count toward Tier A but cannot seed the Semantic Scholar walk;
    their DOIs are returned so candidates matching them are kept out of
    Tier B (a paper lives in exactly one tier).
    """
    text = (PAPERS_DIR / "README.md").read_text()
    tier_a_count = len(re.findall(r"^\| `", text, flags=re.MULTILINE))
    ids = re.findall(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})", text)
    seen: dict[str, None] = {}
    for i in ids:
        seen.setdefault(i, None)
    dois = {
        d.lower()
        for line in text.splitlines()
        if line.startswith("| `")
        for d in re.findall(r"doi\.org/(10\.[^\s)`]+)", line)
    }
    return tier_a_count, list(seen), dois


def fetch_seed(arxiv_id: str, cache_dir: Path) -> dict | None:
    cache = cache_dir / f"{arxiv_id}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    url = f"{API}arXiv:{arxiv_id}?fields=title,year,{NESTED_FIELDS}"
    headers = api_headers()
    backoff = PAUSE_S
    for _ in range(8):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
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


def api_headers() -> dict[str, str]:
    if key := os.environ.get("S2_API_KEY"):
        return {"x-api-key": key}
    return {}


def normalize_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def verify_index() -> int:
    """F8.1: every Tier B row must match the live API record exactly."""
    index = json.loads((PAPERS_DIR / "corpus-index.json").read_text())
    rows = index["tierB"]
    log(f"verifying {len(rows)} Tier B rows against the live API (batch)")
    headers = {**api_headers(), "Content-Type": "application/json"}
    live: dict[str, dict | None] = {}
    for start in range(0, len(rows), 500):
        chunk = rows[start : start + 500]
        body = json.dumps({"ids": [r["s2PaperId"] for r in chunk]}).encode()
        url = API + "batch?fields=title,year,externalIds"
        backoff = PAUSE_S
        for _ in range(8):
            try:
                req = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    results = json.loads(resp.read())
                for r, res in zip(chunk, results, strict=True):
                    live[r["s2PaperId"]] = res
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF_S)
                    continue
                log(f"  batch at {start}: HTTP {e.code}")
                return 1
            except (urllib.error.URLError, TimeoutError):
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF_S)
        else:
            log(f"  batch at {start}: gave up after retries")
            return 1
        time.sleep(PAUSE_S)

    mismatches, stale_refs, unresolved = [], [], []
    for r in rows:
        res = live.get(r["s2PaperId"])
        if not res:
            unresolved.append(r["ref"])
            continue
        # Rows are fetched BY s2PaperId, so identity is anchored; the title
        # is the fabrication check, the external id the staleness check.
        title_ok = normalize_title(res.get("title") or "") == normalize_title(
            r["title"]
        )
        if not title_ok:
            mismatches.append((r["ref"], r["title"], res.get("title")))
            continue
        ext = res.get("externalIds") or {}
        scheme, _, value = r["ref"].partition(":")
        stored_ext = {"arxiv": ext.get("ArXiv"), "doi": ext.get("DOI")}[scheme]
        id_ok = (stored_ext or "").lower() == value.lower()
        if not id_ok and scheme == "doi":
            # DataCite arXiv DOI (10.48550/arXiv.X) ≡ arXiv id X - the
            # same canonicalization the paper store applies.
            m = re.fullmatch(r"10\.48550/arxiv\.(.+)", value, flags=re.IGNORECASE)
            id_ok = bool(m) and (ext.get("ArXiv") or "").lower() == m[1].lower()
        if not id_ok:
            new_ref = (
                f"arxiv:{ext['ArXiv']}" if ext.get("ArXiv") else f"doi:{ext['DOI']}"
            )
            stale_refs.append((r["ref"], new_ref))

    for ref, stored, live_title in mismatches:
        log(f"  MISMATCH {ref}: stored={stored!r} live={live_title!r}")
    for old, new in stale_refs:
        log(f"  stale ref (paper re-published; re-harvest updates): {old} -> {new}")
    if unresolved:
        n = len(unresolved)
        log(f"  unresolved (API no longer returns; re-harvest clears): {n}")
        for ref in unresolved[:10]:
            log(f"    {ref}")
    verified = len(rows) - len(mismatches) - len(stale_refs) - len(unresolved)
    log(
        f"verified {verified}/{len(rows)} identical; {len(mismatches)} mismatches; "
        f"{len(stale_refs)} stale refs; {len(unresolved)} unresolved"
    )
    return 1 if mismatches else 0


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


def is_recognized_venue(p: dict) -> bool:
    return bool(RECOGNIZED_VENUES.search((p.get("venue") or "").strip()))


def score(p: dict, edges: int, this_year: int) -> float:
    year = p.get("year") or 0
    cites = p.get("citationCount") or 0
    infl = p.get("influentialCitationCount") or 0
    freshness = max(0, 5 - (this_year - year)) * 1.6  # fresh precedence
    impact = math.log10(cites + 1) * 2.0
    influence = math.log10(infl + 1) * 1.2  # citations that *used* the work
    connectivity = min(edges, 6) * 1.5  # cited by/citing many seeds
    venue = 0.5 if (p.get("venue") or "").strip() else 0.0
    venue += 1.0 if is_recognized_venue(p) else 0.0  # recognized venue/lab
    open_access = 0.4 if p.get("openAccessPdf") else 0.0  # reproducibility
    return round(freshness + impact + influence + connectivity + venue + open_access, 3)


def propose_tier_a(n: int) -> int:
    """Emit a promotion shortlist: the top-scored Tier B rows with their
    quality metrics, for hand-curation into Tier A (the human writes or
    approves every 'why'; generic LLM-infrastructure papers are skipped
    by the curator, not the script — judgment stays human)."""
    index = json.loads((PAPERS_DIR / "corpus-index.json").read_text())
    rows = sorted(index["tierB"], key=lambda r: -r["score"])[:n]
    print("| Ref | Title | Year | Venue | Cites | Infl | OA | Score | Via |")
    print("| --- | ----- | ---- | ----- | ----- | ---- | -- | ----- | --- |")
    for r in rows:
        title = r["title"].replace("|", "\\|")
        venue = (r.get("venue") or "—").replace("|", "\\|")
        print(
            f"| `{r['ref']}` | {title} | {r['year']} | {venue} "
            f"| {r.get('citationCount', 0)} | {r.get('influentialCitationCount', 0)} "
            f"| {'✓' if r.get('openAccess') else '—'} | {r['score']} "
            f"| {len(r.get('via', []))} |"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--target",
        type=int,
        default=0,
        help="0 (default,) = uncapped: ship every gate-passing, seed-woven "
        "candidate (FR-LIT-8 rev 2); N = capped top-N legacy behavior",
    )
    ap.add_argument("--cache-dir", type=Path)
    ap.add_argument(
        "--verify",
        action="store_true",
        help="verify the existing corpus-index.json against the live API (F8.1)",
    )
    ap.add_argument(
        "--propose-tier-a",
        type=int,
        metavar="N",
        help="print the top-N Tier B rows as a hand-curation shortlist",
    )
    args = ap.parse_args()
    if args.verify:
        return verify_index()
    if args.propose_tier_a:
        return propose_tier_a(args.propose_tier_a)
    if not args.cache_dir:
        ap.error("--cache-dir is required for harvesting")
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    this_year = date.today().year

    tier_a_count, seeds, seed_dois = read_seeds()
    log(f"{tier_a_count} Tier A seeds ({len(seeds)} arXiv-resolvable) from README.md")

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

    def is_seed(pid: str, p: dict) -> bool:
        doi = ((p.get("externalIds") or {}).get("DOI") or "").lower()
        return pid in seed_pids or doi in seed_dois

    def woven(pid: str, p: dict) -> bool:
        """Uncapped inclusion needs domain weave: multiple seed edges, or
        freshness (recent papers haven't had time to accumulate edges)."""
        year = p.get("year") or 0
        return (
            len(edges[pid]) >= MIN_EDGES_UNCAPPED or year >= this_year - FRESH_WINDOW_Y
        )

    passed = [
        (score(p, len(edges[pid]), this_year), pid, p)
        for pid, p in candidates.items()
        if not is_seed(pid, p) and quality_gate(p, this_year)
    ]
    passed.sort(key=lambda t: (-t[0], t[1]))
    if args.target > 0:
        room = args.target - tier_a_count
        picked = passed[:room]
        log(f"capped mode: room {room}")
    else:
        picked = [(s, pid, p) for s, pid, p in passed if woven(pid, p)]
        dropped = len(passed) - len(picked)
        log(
            f"uncapped mode: {len(picked)} woven candidates kept, "
            f"{dropped} gate-passers dropped (single-edge, not fresh)"
        )
    log(
        f"seeds resolved {resolved}/{len(seeds)}; candidates {len(candidates)}; "
        f"passed gate {len(passed)}; picked {len(picked)}"
    )
    if len(picked) + tier_a_count < 1000:
        log("WARNING: corpus below the 1,000-paper floor (FR-LIT-8)")

    def ref_of(p: dict) -> str:
        ext = p.get("externalIds") or {}
        if ext.get("ArXiv"):
            return f"arxiv:{ext['ArXiv']}"
        return f"doi:{ext['DOI']}"

    index = {
        "generatedAt": date.today().isoformat(),
        "pipeline": "scripts/corpus_harvest.py (FR-LIT-8; D8/D36)",
        "tierA": {
            "count": tier_a_count,
            "arxivResolvable": len(seeds),
            "source": "docs/papers/README.md",
        },
        "scoringVersion": SCORING_VERSION,
        "tierB": [
            {
                "ref": ref_of(p),
                "s2PaperId": pid,
                "title": p["title"],
                "year": p["year"],
                "venue": (p.get("venue") or "").strip() or None,
                "recognizedVenue": is_recognized_venue(p),
                "citationCount": p.get("citationCount") or 0,
                "influentialCitationCount": p.get("influentialCitationCount") or 0,
                "openAccess": bool(p.get("openAccessPdf")),
                "publicationTypes": p.get("publicationTypes") or None,
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
        "connectivity-ranked. Tier A seeds without an arXiv id count toward "
        "the corpus total but cannot seed the walk. "
        "`via` = seed arXiv ids that discovered it. "
        "Verify any row at `https://api.semanticscholar.org/graph/v1/paper/"
        "<ref>`.",
        "",
        f"**{len(picked)} papers** (+ {tier_a_count} Tier A seeds = "
        f"{len(picked) + tier_a_count} total).",
        "",
        "| Ref | Title | Year | Venue | Cites | Infl | OA | Score | Via seeds |",
        "| --- | ----- | ---- | ----- | ----- | ---- | -- | ----- | --------- |",
    ]
    for s, pid, p in picked:
        title = p["title"].replace("|", "\\|")
        venue = ((p.get("venue") or "").strip() or "—").replace("|", "\\|")
        infl = p.get("influentialCitationCount") or 0
        lines.append(
            f"| `{ref_of(p)}` | {title} | {p['year']} | {venue} | "
            f"{p.get('citationCount') or 0} | {infl} | "
            f"{'✓' if p.get('openAccessPdf') else '—'} | {s} | {len(edges[pid])} |"
        )
    (PAPERS_DIR / "CORPUS.md").write_text("\n".join(lines) + "\n")
    log(f"wrote corpus-index.json + CORPUS.md ({len(picked) + tier_a_count} papers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
