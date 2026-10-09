# StudyLoop

StudyLoop helps researchers plan and run human–AI developer experiments. Record the design and analysis, estimate recruitment, collect versioned measures, inspect control-arm signals, and export the study record for replication.

Power estimates report their assumptions and simulation uncertainty. Pilot sessions are tagged and excluded from confirmatory analysis. Audit signals are not proof of whether AI was used outside the capture boundary.

## Run locally

```bash
uv sync --all-packages
npm --prefix platform ci
npm --prefix platform run build
uv run python -m middleware
```

Open http://127.0.0.1:8000. The server resolves `platform/dist` from the repository root, logs its build hash, and fails with the full path if the build is missing. `MIDDLEWARE_API_ONLY=1` explicitly enables operation without the frontend.

To load the protocol v6 example:

```bash
MIDDLEWARE_PROTOCOL=protocol/examples/planner-v6.yaml uv run python -m middleware
```

The example contains configuration, not collected evidence. Supply actual task materials and tool versions before recruitment. Existing protocol versions 1–5 remain readable; their string measures remain untyped.

The design conversation and model-assisted matching share `ministral-14b-latest` by default. Set `LLM_API_KEY` for a hosted provider or `LLM_BASE_URL` for a compatible local server. Use `LLM_MODEL` for a shared model and `LLM_DESIGN_MODEL` for a design-only override; legacy `MISTRAL_*` settings remain supported. Record the exact tool/model version used in each study condition. See [server configuration](middleware/README.md).

## Study workflow

1. Record a protocol with two conditions and a supported, fixed analysis.
2. Open **Plan** to enter effects, variance, distribution, power, and dropout assumptions. Save the recruitment plan against the protocol hash.
3. Connect participants with the [StudyLoop extension](extension/README.md). Protocol-declared surveys and the pre-task form are captured with instrument versions and hashes.
4. In **Data**, tag pilot sessions and record audit inclusion decisions with reasons. Update the plan from real tagged pilot outcomes. A pilot below eight participants is explicitly flagged.
5. Export the data bundle, design card (JSON/Markdown), and replication kit. A re-run records `rerunOf` and compares designs without pooling data.

Read [planner methods, API and limits](docs/planner.md), the [v6 example](protocol/examples/planner-v6.yaml), and [research evaluation](docs/research-evaluation.md).

## Validate

```bash
uv run pytest protocol/tests analysis/tests middleware/tests metrics/tests agent-capture/tests curated/tests
npm --prefix extension run check
npm --prefix platform run check
```

Planner numerical tests check nominal alpha within 0.015 and agreement with normal-theory power within 0.06 for the tested configurations. These are computational checks. Audit sensitivity/specificity require independent labels from real calibration sessions; the platform makes no accuracy claim before those exist.
