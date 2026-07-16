# Analysis corpus - do not "fix" or delete

These files are **deliberately imperfect sample code**: the fixed
measurement target for the static-metrics extractors (`metrics/src/`), not
part of the framework's own codebase. Deep nesting, over-long lines,
erratic indentation, duplicate method names, and sparse comments are the
*point* - they exercise the 9-metric cognitive-load matrix and give the
verification spot-checks in `metrics/docs/implementation_plan.md` stable,
hand-countable values (e.g. `weather.py` Halstead effort 5315.26).

They are excluded from ruff (root `pyproject.toml`) and used by:

- the default target of `uv run python metrics/src/main.py`
- the `__main__` demo in `metrics/src/parsers/ts_parser.py`
- the hand-verified numbers recorded in the implementation plan

Editing them silently invalidates those recorded values; if you must change
the corpus, re-run the plan's verification section and update its numbers.
