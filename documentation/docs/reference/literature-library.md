# Keep the literature library current

StudyLoop ships a paper corpus that powers template rankings and the literature
suggestions in the design conversation. The server can refresh the library with
newer papers and screen them for relevance. You can review the candidates and record
decisions by hand.

## Refresh and review

```bash
uv run --no-sync --env-file .env.local python -m middleware corpus-refresh --dry-run
uv run --no-sync --env-file .env.local python -m middleware corpus-refresh
uv run --no-sync --env-file .env.local python -m middleware corpus-review --limit 20
uv run --no-sync --env-file .env.local python -m middleware corpus-decide --ref arxiv:2610.00000 --decision accept --note "Reviewed title and abstract; relevant to this study area"
uv run --no-sync --env-file .env.local python -m middleware corpus-decide --ref arxiv:2610.00001 --decision reject --note "Model benchmark without developer participants"
```

The `--ref` values are placeholders: list the real candidates first and decide on
those. `--dry-run` fetches and reports without storing anything.

- **Manual refresh** searches arXiv and Semantic Scholar for recent metadata and
  stores papers it has not seen as candidates. Use `corpus-candidates` to list them.
- **Accepting** adds the candidate to the corpus as a tier C paper, with your note,
  and makes it searchable. Accepted papers live in the database, so back it up.
  They do not count toward completion of the checked-in core corpus.
- **Rejecting** records a human decision. For a paper already in the corpus, it
  hides the paper from search. Automatic screening respects human decisions.
- **The Literature tab** shows when the last refresh ran and how many candidates
  await review, and identifies a refresh that was partial or failed.

## Queries and schedule

Queries live in `docs/papers/refresh-queries.json`, or in the file named by
`MIDDLEWARE_REFRESH_QUERIES` or `--queries`. A server that bootstraps the corpus
refreshes every 24 hours by default. Set `MIDDLEWARE_REFRESH_INTERVAL_H=6` for a
six-hour interval, or `MIDDLEWARE_REFRESH_INTERVAL_H=off` for manual refreshes.

Scheduled refreshes also screen the new candidates, and only those. Screening
compares each candidate with the papers a person chose as examples: the seed
papers and anything you accept or reject. It can add a relevant paper to the
corpus, dismiss an off-topic one (a reversible status), or leave a paper for review
when its relevance is uncertain or its metadata is missing.

The comparison uses SPECTER2 vectors from Semantic Scholar. The newest preprints
often have none yet. If your model route is Mistral's API (`LLM_API_KEY` with the
default or a Mistral `LLM_BASE_URL`), the titles and abstracts of those candidates
and of the example papers go to `mistral-embed`, which has its own request quota
apart from the chat models. Without that route they wait for the next run or for
you. The manual `corpus-refresh` command collects candidates but does not screen
them.

Every refresh records its window, counts and source errors. Only a fully successful
run advances the date watermark, and a retry overlaps the last run by one day. A
refresh that starts while another recent one is still running is refused. A failed
source gives a partial run when another source succeeds, and no source failure is
counted as a success.

## Rate limits and licences

arXiv requests are paced to at least three seconds apart. Semantic Scholar requests
are paced to one per second and retried a bounded number of times, and keyless
requests can still receive 429 responses. Set `MIDDLEWARE_S2_API_KEY` if you have a
key, and `MIDDLEWARE_CONTACT_EMAIL` to give arXiv a contact address.

Paper metadata includes data from Semantic Scholar and arXiv. Abstracts of
recommended papers are left out of conversation exports and replication kits.
Review Semantic Scholar's caching and reuse terms before you store or share
abstracts. Uploaded researcher files remain the researcher's responsibility.

## Curation

`corpus-curate` can change which existing corpus papers appear in search. Review
`corpus-curate --dry-run` first to see what would change using stored metadata. See
[Configuration](configuration.md#commands) for the other corpus commands.

## Next steps

- [Literature](../platform/library.md), the researcher's view
- [Configuration](configuration.md)
