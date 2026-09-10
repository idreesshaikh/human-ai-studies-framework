# Code metrics

Measures structural properties of Python code for a study. Tree-sitter supplies
function structure, Radon supplies Halstead and comment measures, and optional
SonarQube integration supplies cognitive complexity.

From the repository root:

```bash
uv run python metrics/src/main.py metrics/corpus --out results/metrics
uv run pytest metrics
```

Use `--help` for study/session identity, output format, and SonarQube options.
An unavailable SonarQube measurement is reported as missing, never as zero.

`src/main.py` coordinates discovery and export. `src/parsers/` and
`src/analyzers/` implement measurements. The files in `corpus/` are deliberately
imperfect test specimens; changing them changes the expected measurements.

See [metric definitions](docs/static_code_metrics.md) for interpretation and
limitations. These measurements describe code structure, not developer ability
or overall software quality.
