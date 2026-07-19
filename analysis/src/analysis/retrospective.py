"""Self-improvement retrospective (FR-META-2) - the framework proposes its
own improvements, a human approves them.

``analysis retrospective`` collects the operational-findings log (FR-META-1),
the facilitator's ``findings.md``, and recipe-coverage aggregates, then has
Mistral (D32 rev 2) draft a **changelist proposal**
(SRS amendments / protocol-schema changes / instrument-config changes /
rejected ideas), each item citing the findings that evidence it.

Two hard boundaries:

- **FR-ETH-4 / NFR-5:** the prompt is built from findings + *aggregates only*
  - no participant rows, no session/participant ids. :func:`build_prompt` is
    the choke point the grep-the-output test guards.
- **Human gate:** the proposal is *inert* - a Markdown file. The framework
  never edits its own requirements unattended; "self-evolving" means
  *self-proposing*. Accepted items are applied by the researcher as ordinary,
  change-managed edits to ``requirements/srs.md`` + ``traceability.md``.

Offline-degradable: without ``MISTRAL_API_KEY`` it emits
the collected evidence bundle plus a proposal template for the researcher to
complete by hand - the evidence is still fully assembled and cited.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

MISTRAL_MODEL = "mistral-small-latest"

SYSTEM_PROMPT = (
    "You are drafting a self-improvement proposal for a "
    "requirements-engineered human-AI study framework. You are given the "
    "framework's own operational-findings log and the facilitator's notes - "
    "operational defects and aggregate coverage ONLY; you have no participant "
    "data and must never ask for any. Draft a changelist PROPOSAL, inert "
    "until a human reviews it, with exactly these sections:\n"
    "## SRS amendments (per requirement ID: keep / amend / add, each citing "
    "the finding(s) that evidence it)\n"
    "## Protocol-schema changes\n"
    "## Instrument config changes\n"
    "## Explicitly rejected ideas (with why)\n"
    "Cite every proposed change by the requirement ID and finding it rests "
    "on. Propose; do not decide - the researcher applies accepted items as "
    "ordinary change-managed SRS edits."
)


# ------------------------------------------------------------- collection


def _get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=10) as res:
        return json.loads(res.read())


def collect_evidence(
    server: str | None,
    study_id: str,
    findings_md: str | Path | None,
    *,
    fetch=None,
) -> dict:
    """Assemble the retrospective's evidence - findings + facilitator notes +
    coverage aggregates. ``fetch`` is the GET seam (tests inject a stub);
    network failures degrade to empty rather than raising."""
    fetch = fetch or _get_json
    findings: list[dict] = []
    coverage: dict = {}
    if server:
        base = server.rstrip("/")
        try:
            findings = fetch(f"{base}/findings") or []
        except OSError:
            findings = []
        try:
            status = fetch(f"{base}/studies/{study_id}/status") or {}
            coverage = _coverage(status)
        except OSError:
            coverage = {}

    notes = ""
    if findings_md and Path(findings_md).is_file():
        notes = Path(findings_md).read_text()

    return {
        "studyId": study_id,
        "findings": findings,
        "facilitatorNotes": notes,
        "coverage": coverage,
    }


def _coverage(status: dict) -> dict:
    """Aggregate coverage only - NO participant/session ids (FR-ETH-4)."""
    return {
        "currentPhase": status.get("lifecycle", {}).get("currentPhase"),
        "plannedParticipants": status.get("plannedParticipants"),
        "sessionCount": len(status.get("sessions", [])),
        "researchQuestions": [
            {
                "id": rq.get("id"),
                "recipes": rq.get("recipes", []),
                "recipeRuns": rq.get("recipeRuns", []),
            }
            for rq in status.get("researchQuestions", [])
        ],
    }


# ---------------------------------------------------------- prompt + draft


def build_prompt(evidence: dict) -> str:
    """The user-message body for the model - findings + aggregates only. This is
    the FR-ETH-4 choke point: it must contain no participant-row data."""
    lines = [
        f"# Retrospective evidence for study {evidence['studyId']}",
        "",
        "## Operational findings log (FR-META-1)",
    ]
    if evidence["findings"]:
        for f in evidence["findings"]:
            req = f.get("requirementId") or "?"
            kind = f.get("kind") or "finding"
            lines.append(f"- [{req}] ({kind}) {f.get('message', '')}")
    else:
        lines.append("- (none logged)")

    cov = evidence.get("coverage") or {}
    lines += ["", "## Coverage aggregates (no participant data)"]
    lines.append(f"- current phase: {cov.get('currentPhase')}")
    lines.append(f"- planned participants: {cov.get('plannedParticipants')}")
    lines.append(f"- sessions collected: {cov.get('sessionCount')}")
    for rq in cov.get("researchQuestions", []):
        ran = ", ".join(rq.get("recipeRuns", [])) or "none run"
        lines.append(f"- {rq['id']}: recipes {rq.get('recipes')} - ran: {ran}")

    if evidence["facilitatorNotes"]:
        lines += [
            "",
            "## Facilitator notes (findings.md)",
            "",
            evidence["facilitatorNotes"].strip(),
        ]
    return "\n".join(lines) + "\n"


def _post_json(url: str, body: dict, headers: dict[str, str]) -> dict:
    """POST JSON, return parsed JSON - the network seam tests stub out."""
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


class MistralClient:
    """Single-turn draft via Mistral's chat-completions REST API (D32)."""

    def __init__(self, api_key: str, model: str = MISTRAL_MODEL, post=_post_json):
        self.api_key = api_key
        self.model = model
        self.post = post

    def draft(self, system: str, prompt: str) -> str:
        res = self.post(
            "https://api.mistral.ai/v1/chat/completions",
            {
                "model": self.model,
                "max_tokens": 4096,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            {"Authorization": f"Bearer {self.api_key}"},
        )
        msg = (res.get("choices") or [{}])[0].get("message", {})
        return str(msg.get("content") or "")


def make_client():
    """A Mistral client (D32 rev 2), or None when no key is set (offline
    path). Never raises."""
    if key := os.environ.get("MISTRAL_API_KEY"):
        return MistralClient(key)
    return None


def draft_with_llm(evidence: dict, client) -> str:
    """Ask the configured model for the proposal (D32); no participant data
    crosses the boundary."""
    return client.draft(SYSTEM_PROMPT, build_prompt(evidence))


def evidence_bundle(evidence: dict) -> str:
    """Offline fallback: the assembled evidence + a proposal template the
    researcher completes by hand. The findings are fully cited already."""
    return (
        "# Retrospective proposal (TEMPLATE - complete by hand)\n\n"
        "The knowledge assistant was unavailable (no `MISTRAL_API_KEY`); "
        "this bundle collects the evidence so you can draft the proposal "
        "manually. It is **inert** until you apply accepted items as ordinary, "
        "change-managed edits to `requirements/srs.md` + "
        "`requirements/traceability.md` (new IDs, supersessions, log entry).\n\n"
        "---\n\n"
        + build_prompt(evidence)
        + "\n---\n\n## SRS amendments\n\n_Per requirement ID: keep / amend / "
        "add, citing the findings above._\n\n"
        "## Protocol-schema changes\n\n_..._\n\n"
        "## Instrument config changes\n\n_..._\n\n"
        "## Explicitly rejected ideas\n\n_...with why._\n"
    )


def build_proposal(evidence: dict, client) -> tuple[str, bool]:
    """Return (proposal_markdown, used_llm)."""
    if client is not None:
        body = draft_with_llm(evidence, client)
        header = (
            "# Retrospective changelist proposal (FR-META-2)\n\n"
            "> **Inert until reviewed.** Draft only - apply accepted items as "
            "ordinary change-managed edits to `requirements/srs.md` + "
            "`requirements/traceability.md`. The framework never edits its own "
            "requirements unattended.\n\n"
        )
        return header + body + "\n", True
    return evidence_bundle(evidence), False


# ------------------------------------------------------------------- CLI


def _proposal_filename() -> str:
    """``<date>-proposal.md``; date is reproducible via SOURCE_DATE_EPOCH."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        from datetime import UTC, datetime

        date = datetime.fromtimestamp(int(epoch), tz=UTC).date().isoformat()
    else:
        from datetime import date as _date

        date = _date.today().isoformat()
    return f"{date}-proposal.md"


def cmd_retrospective(protocol: dict, study_id: str, args) -> int:
    findings_md = getattr(args, "findings_md", None)
    evidence = collect_evidence(args.server, study_id, findings_md)
    client = make_client()
    proposal, used_llm = build_proposal(evidence, client)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / _proposal_filename()
    path.write_text(proposal)

    print(f"retrospective proposal: {path}")
    print(
        f"  evidence: {len(evidence['findings'])} finding(s)"
        + (" + facilitator notes" if evidence["facilitatorNotes"] else "")
    )
    print(
        "  drafted with the configured model (D32 bounds: findings + aggregates only)"
        if used_llm
        else "  no MISTRAL_API_KEY - emitted the evidence "
        "bundle + template for manual drafting"
    )
    print(
        "  HUMAN GATE: the proposal is inert. Review it, then apply accepted "
        "items as change-managed SRS/traceability edits."
    )
    return 0
