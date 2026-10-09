"""Freeze/check mapping evaluations without turning synthetic labels into research."""

import argparse
import json
from pathlib import Path

from middleware.assistant import make_design_client, model_name
from middleware.evaluation import (
    Benchmark,
    Case,
    Prediction,
    model_predictions,
    rules_predictions,
    score,
)
from middleware.evidence_mapping import EvidenceContext, digest
from protocol.evidence import load_evidence_map

ROOT = Path(__file__).resolve().parents[1]


def save(path: str, document: dict) -> None:
    target = Path(path).resolve()
    if target.is_relative_to(ROOT) and not target.is_relative_to(
        ROOT / ".research-artifacts"
    ):
        raise ValueError(
            "Generated research artifacts belong in .research-artifacts/ "
            "or outside the repository"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


def smoke_benchmark(evidence: dict) -> Benchmark:
    context = EvidenceContext(
        query="Does AI assistance change completion time?",
        population="Novice Python developers",
        task="Fix a Python bug",
        construct="completion-time",
        producers=["task-harness"],
        instruments=["task-harness"],
        confirmedRelationIds=[r["id"] for r in evidence["relations"]],
    )
    cases = []
    for name, change, status in [
        ("external-capture", {}, "conditional"),
        ("missing-producer", {"producers": []}, "incompatible"),
        ("unconfirmed-source", {"confirmedRelationIds": []}, "insufficient-evidence"),
        (
            "different-population",
            {"population": "Experienced Rust developers"},
            "insufficient-evidence",
        ),
    ]:
        changed = EvidenceContext.model_validate({**context.model_dump(), **change})
        cases.append(
            Case(
                id=name,
                scenario_family="synthetic-debugging",
                split="test",
                study_ids=[s["id"] for s in evidence["studies"]],
                context=changed,
                expected={s["id"]: status for s in evidence["studies"]},
            )
        )
    return Benchmark(
        version="synthetic-smoke-1",
        map_digest=digest(evidence),
        label_provenance="synthetic",
        reviewers=[],
        review_notes="Invented checks; no empirical or expert benchmark claim.",
        cases=cases,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        help="Frozen benchmark JSON; omit for explicit synthetic smoke checks",
    )
    parser.add_argument(
        "--map", default=str(ROOT / "protocol/examples/evidence-workflow-demo.json")
    )
    parser.add_argument(
        "--predictions",
        help="External predictions JSON; omit to run deterministic rules",
    )
    parser.add_argument(
        "--system-version",
        required=True,
        help="Immutable model/architecture version or commit",
    )
    parser.add_argument("--allow-synthetic", action="store_true")
    parser.add_argument(
        "--runner", choices=["rules", "direct", "propose-critic"], default="rules"
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default=model_name(design=True))
    parser.add_argument(
        "--output", default=str(ROOT / ".research-artifacts/mapping-evaluation.json")
    )
    args = parser.parse_args()
    evidence = load_evidence_map(args.map)
    benchmark = (
        Benchmark.model_validate(json.loads(Path(args.benchmark).read_text()))
        if args.benchmark
        else smoke_benchmark(evidence)
    )
    benchmark.verify(evidence, allow_synthetic=args.allow_synthetic)
    calls = []
    if args.predictions:
        rows = [
            Prediction.model_validate(row)
            for row in json.loads(Path(args.predictions).read_text())
        ]
    elif args.runner == "rules":
        rows = rules_predictions(benchmark, evidence)
    else:
        client = make_design_client() if args.live else None
        if client is None:
            parser.error("Live experiments require --live and a configured model route")
        client.model = args.model

        def request(prompt):
            response = client.post(
                client.base_url,
                {
                    "model": client.model,
                    "max_tokens": 1200,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                'Return JSON only: {"decisions":[{"candidate_id":"id",'
                                '"status":"conditional","confidence":null}]}. '
                                "Allowed status: compatible, conditional, "
                                "incompatible, "
                                "insufficient-evidence, or null for abstention. "
                                "Use only the supplied evidence and constraints. "
                                "Reported method use and unreviewed sources do "
                                "not justify recommendations."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
                client.headers,
            )
            calls.append(
                {"resolvedModel": response.get("model"), "usage": response.get("usage")}
            )
            return json.loads(response["choices"][0]["message"]["content"])

        rows = model_predictions(
            benchmark,
            evidence,
            request,
            stages=2 if args.runner == "propose-critic" else 1,
        )
    report = score(benchmark, rows)
    save(
        args.output,
        {
            "systemVersion": args.system_version,
            "benchmark": benchmark.model_dump(mode="json"),
            "predictions": [row.model_dump() for row in rows],
            "report": report,
            "runner": args.runner,
            "providerCalls": calls,
        },
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
