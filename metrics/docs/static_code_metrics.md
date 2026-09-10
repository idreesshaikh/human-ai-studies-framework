# Static code metrics

The optional `metrics` producer measures the structure of a checked-out Python
workspace. It describes files and functions; it does not measure developer
ability or software quality by itself.

## Toolchain

- Tree-sitter parses functions, parameters, nesting, identifiers, and scope.
- Radon supplies Halstead effort and comment-to-code ratio.
- Plain-text analysis supplies indentation and line-width measures.
- SonarQube can supply cognitive complexity. If it is unavailable, the value
  is missing and the run is marked `degraded`; missing is never treated as zero.

## Measures

| Level | Measures | Source |
| --- | --- | --- |
| Function | parameter count, nesting penalty, average identifier length, variable-scope distance, Halstead effort | Tree-sitter and Radon |
| File | indentation variance, maximum and mean line width, comment ratio, Halstead effort total | text analysis and Radon |
| File (optional) | cognitive complexity | SonarQube |

Every row carries the study join keys, source, metric-set name, schema version,
run id, run status, and a stable `metricId`. The JSONL and CSV outputs can be
posted to the middleware metrics endpoint, but the local files remain the
recovery source when the server is unavailable.

Run it from the repository root:

```bash
uv run python metrics/src/main.py <workspace> --out results/metrics
uv run pytest metrics
```

The files in `metrics/corpus/` are deliberately small, imperfect test
specimens. Changing them changes the expected measurements.
