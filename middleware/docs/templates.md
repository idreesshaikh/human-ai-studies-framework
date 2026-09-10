# Reviewing candidate templates

The mining script groups corpus papers by recurring design vocabulary and
proposes YAML templates. A title or abstract match does not establish that the
papers share a valid study design. Read the supporting methods before promotion.

From the repository root:

```bash
uv run python -m middleware corpus-import
uv run python scripts/mine_templates.py
uv run python scripts/mine_templates.py --gaps
```

These commands report candidates and uncovered vocabulary. Add `--write` to
write qualifying candidates under `templates/drafts/`.

Review the research question, comparison, sampling assumptions, instruments,
recipes, and cited papers. Check the resulting protocol with the schema and the
analysis plan against appropriate synthetic data. A schema pass checks structure,
not scientific validity.

Promote a reviewed candidate by adding its YAML to `templates/registry/` in a
normal contribution. Validate the registry with:

```bash
uv run python -m middleware templates
```

There is no automatic promotion command or moderation service.
