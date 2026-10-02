# Experimental mining package

`curated` is a small, isolated research lane for turning an existing archive
into content-free event rows.  It is not used by the live PHOENIX server,
TERN, or the default analysis workflow.

## What exists

- a sampling-frame and cursor contract;
- salted actor pseudonyms;
- versioned authorship heuristics and validity-threat records;
- a local JSON, JSONL, or CSV archive adapter used by the tests.

## What does not exist

There is no GitHub/API adapter, mining command, background job, middleware
ingest client, snapshot/metrics integration, or end-to-end mining study. The
package is not a finished observational-study workflow and is outside the
feature-frozen release boundary.

Run its focused tests with:

```bash
uv run pytest curated
```

Keep it optional and independent of the live packages. Promotion is out of
scope for this release; changing that boundary would require a complete,
separately reviewed path from declared frame through analysis. Nothing in the
live product depends on it.
