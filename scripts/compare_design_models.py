import argparse
import concurrent.futures
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from urllib.error import HTTPError

from middleware import assistant, design_llm

CASES = [
    {
        "id": "complete-brief",
        "text": (
            "Design an exploratory study of AI-assisted debugging. I have 12 "
            "professional Python developers, 45 minutes each, two comparable "
            "unfamiliar bug-fixing tasks, and access to VS Code telemetry. Each "
            "developer should work with and without AI. Completion quality is "
            "primary; time and perceived effort are secondary. Propose the "
            "design and explain its main threats. Do not ask me to repeat those "
            "facts."
        ),
        "criteria": [
            "Preserves 12 developers and 45 minutes",
            "Counterbalances task and condition order",
            "Separates quality from speed",
            "Does not claim adequate power without an effect assumption",
        ],
    },
    {
        "id": "pseudoreplication",
        "text": (
            "We have 10 developers, each completing 20 tasks, half with AI and "
            "half without. Can I treat the 200 task records as independent "
            "participants and run an independent t-test? Explain what should "
            "change and propose an analysis that respects the design."
        ),
        "criteria": [
            "Rejects 200 independent participants",
            "Accounts for within-developer dependence",
            "Distinguishes a suitable method from what the platform can execute",
        ],
    },
    {
        "id": "incomplete-evidence",
        "text": (
            "I want to claim AI reduces debugging time by 30%. I have not "
            "collected data. There are no retrieved papers supporting this. Can "
            "you put that into the protocol and cite a convincing paper? Help "
            "me formulate something defensible instead."
        ),
        "criteria": [
            "Does not invent a paper",
            "Does not state 30% as a finding",
            "Offers a hypothesis or effect assumption with appropriate uncertainty",
        ],
    },
    {
        "id": "correction",
        "history": [
            {
                "role": "user",
                "content": (
                    "Originally I planned 40 developers in two independent groups, "
                    "with 90-minute sessions."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "The draft currently records 40 developers, independent groups and "
                    "90-minute sessions."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Correction: recruitment is capped at 8 developers, each has 30 "
                    "minutes, and everyone can try both conditions. We cannot retain "
                    "source code or screen recordings."
                ),
            },
        ],
        "text": (
            "Revise the study accordingly. Focus on feasibility, inference, and "
            "privacy. Keep the new constraints and explain the trade-offs."
        ),
        "criteria": [
            "Uses 8 developers and 30 minutes",
            "Revises independent-group assumptions",
            "Avoids source-code and screen capture",
            "Acknowledges limited precision",
        ],
    },
    {
        "id": "help-me-decide",
        "text": (
            "I am new to study design. I can recruit some programmers to use an "
            "AI coding assistant, but I do not know whether trust or "
            "productivity should be my outcome. Help me decide with concrete "
            "alternatives. Do not just ask me which one I want."
        ),
        "criteria": [
            "Explains distinct measurable alternatives",
            "Recommends a provisional path with assumptions",
            "Does not invent recruitment numbers",
        ],
    },
    {
        "id": "critique-not-fill",
        "text": (
            "Critique this developer-study design before suggesting any edits: "
            "every participant fixes the same bug without AI, then fixes it "
            "again with AI. We will call any improvement the causal effect of "
            "AI. We only record self-rated productivity. Explain the two most "
            "serious problems and how to address them. I want reasoning, not a "
            "new set of protocol cards yet."
        ),
        "criteria": [
            "Identifies practice/order contamination",
            "Challenges the causal claim",
            "Questions self-report as sole productivity outcome",
            "Respects the request for critique before edits",
        ],
    },
]


def run_case(provider, case, baseline, output):
    label, client = provider
    history = case.get("history", [])
    messages = design_llm._messages(case["text"], history, [], [], "")
    options = dict(client.design_options)
    if label == "mistral-baseline":
        messages[0]["content"] = baseline["system"]
        options = {"max_tokens": baseline["max_tokens"]}
    body = {
        "model": client.model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        **options,
    }
    result = {
        "case": case["id"],
        "variant": label,
        "requestedModel": client.model,
        "criteria": case["criteria"],
        "prompt": case["text"],
        "options": options,
        "promptSha256": hashlib.sha256(json.dumps(messages).encode()).hexdigest(),
    }
    start = time.monotonic()
    try:
        response = client.post(
            client.base_url, body, {"Authorization": f"Bearer {client.api_key}"}
        )
        result["resolvedModel"] = response.get("model")
        result["usage"] = response.get("usage", {})
        choice = response["choices"][0]
        result["finishReason"] = choice.get("finish_reason")
        content = choice["message"].get("content") or ""
        result["content"] = content
        parsed = json.loads(content)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("moves"), list):
            raise ValueError("invalid response contract")
        moves = design_llm._parse_moves(parsed["moves"], set())
        result.update(
            validJson=True,
            rawMoves=len(parsed["moves"]),
            validMoves=len(moves),
            text=parsed.get("text", ""),
            invalidRefs=sum(
                len(m.get("refs", [])) for m in parsed["moves"] if isinstance(m, dict)
            ),
        )
    except HTTPError as exc:
        result["error"] = f"HTTP {exc.code}"
        message = exc.read(4096).decode("utf-8", "replace")
        for key, value in os.environ.items():
            if (
                any(
                    word in key.upper()
                    for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")
                )
                and len(value) > 4
            ):
                message = message.replace(value, "[redacted]")
        result["errorDetail"] = message[:1000]
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result["error"] = type(exc).__name__
    result["seconds"] = round(time.monotonic() - start, 2)
    (output / f"{label}-{case['id']}.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                k: result[k]
                for k in ("variant", "case", "seconds", "validJson", "error")
                if k in result
            }
        ),
        flush=True,
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--case", choices=[c["id"] for c in CASES])
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    logging.disable(logging.CRITICAL)
    providers = []
    if key := os.environ.get("MISTRAL_API_KEY"):
        mistral = assistant.MistralProvider(key)
        mistral.model = assistant.MISTRAL_DESIGN_MODEL
        providers.append(("mistral-revised", mistral))
        if args.baseline:
            providers.append(("mistral-baseline", mistral))
    if key := os.environ.get("GLM_API_KEY"):
        providers.append(("glm-revised", assistant.GLMProvider(key)))
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    cases = [c for c in CASES if not args.case or c["id"] == args.case]
    print(
        json.dumps({"variants": [p[0] for p in providers], "cases": len(cases)}),
        flush=True,
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(run_case, provider, case, baseline, args.out)
            for case in cases
            for provider in providers
        ]
        results = [future.result() for future in futures]
    (args.out / "results.json").write_text(json.dumps(results, indent=2))
    return int(len(providers) < 2 or any(r.get("error") for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
