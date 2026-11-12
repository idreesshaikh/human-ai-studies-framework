"""Review warnings for a protocol's ``aiAccess`` section.

A warning names a gap in how a study confirms (or fails to confirm) that a
condition did or did not use AI. It is an advisory for the researcher; it never
blocks a protocol and never claims that non-use was verified.
"""

# AI-use routes that IDE telemetry is not expected to observe. Task 8 replaces
# this with the measured result and a citation comment.
UNVERIFIED_ROUTES: tuple[str, ...] = (
    "paste from a browser chatbot",
    "retyping from another screen",
    "CLI agent without hooks",
)

# Where UNVERIFIED_ROUTES comes from. "design" means the routes follow from what
# the capture is built to observe, with no measurement behind them; Task 8 sets
# "calibration" once a calibration run backs the list. Only the exact value
# "calibration" may be worded as a measured result.
UNVERIFIED_ROUTES_SOURCE: str = "design"

# Channels that can confirm non-use (verification), and means that prevent use
# in the first place (enforcement). Anything else rests on self-report or on
# telemetry that misses the routes above.
_CONFIRMING_VERIFICATION = frozenset({"screen-recording", "proctor"})
_PREVENTING_ENFORCEMENT = frozenset(
    {"locked-environment", "screen-recording", "proctor"}
)


def _warning(
    code: str,
    message: str,
    suggestions: list[str],
    *,
    condition: str | None = None,
    routes: list[str] | None = None,
) -> dict:
    return {
        "code": code,
        "condition": condition,
        "message": message,
        "unverifiableRoutes": routes or [],
        "suggestions": suggestions,
    }


def _channels(policy: dict, field: str) -> set[str] | None:
    """The channel names in ``policy[field]``; None unless a list of strings."""
    value = policy.get(field)
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return set(value)
    return None


def _unverifiable(policy: object) -> bool:
    """True for a well-formed policy that disallows AI with no way to confirm."""
    if not isinstance(policy, dict) or policy.get("aiAllowed") is not False:
        return False
    verification = _channels(policy, "verification")
    enforcement = _channels(policy, "enforcement")
    if verification is None or enforcement is None:
        return False
    return not (_CONFIRMING_VERIFICATION & verification) and not (
        _PREVENTING_ENFORCEMENT & enforcement
    )


def _unverifiable_message(name: str) -> str:
    routes = ", ".join(UNVERIFIED_ROUTES)
    head = (
        f"Condition '{name}' disallows AI but relies only on channels that "
        "cannot confirm non-use. "
    )
    if UNVERIFIED_ROUTES_SOURCE == "calibration":
        return (
            head
            + f"In StudyLoop's calibration, IDE telemetry did not register: {routes}."
        )
    return head + f"StudyLoop's IDE telemetry is not designed to observe: {routes}."


def ai_access_warnings(protocol: dict) -> list[dict]:
    """Review warnings for ``protocol``; empty when nothing needs attention.

    ``protocol`` may be an unvalidated draft. Malformed ``aiAccess`` content is
    skipped without a warning or an exception: schema validation reports it.
    """
    if not isinstance(protocol, dict):
        return []
    ai_access = protocol.get("aiAccess")
    if ai_access is None or ai_access == {}:
        if not protocol.get("controlConditions"):
            return []
        return [
            _warning(
                "ai-access-undeclared",
                "This protocol has control conditions but does not declare "
                "whether each condition may use AI, how that is enforced, or "
                "how it is checked.",
                [
                    "Add an aiAccess section that states the AI policy, "
                    "enforcement and verification for each condition."
                ],
            )
        ]
    if not isinstance(ai_access, dict):
        return []

    warnings = []
    conditions = ai_access.get("conditions")
    for name, policy in (conditions if isinstance(conditions, dict) else {}).items():
        if _unverifiable(policy):
            warnings.append(
                _warning(
                    "ai-access-unverifiable",
                    _unverifiable_message(str(name)),
                    [
                        "Lock the environment or record the screen for this condition.",
                        "Analyse by assigned condition (ITT) and add a "
                        "contamination sensitivity analysis.",
                    ],
                    condition=str(name),
                    routes=list(UNVERIFIED_ROUTES),
                )
            )

    strategy = ai_access.get("deviationStrategy")
    if (
        isinstance(strategy, str)
        and strategy != "itt"
        and ai_access.get("sensitivityAnalysis") is not True
    ):
        warnings.append(
            _warning(
                "deviation-without-sensitivity",
                f"The deviation strategy is '{strategy}' and no contamination "
                "sensitivity analysis is planned, so the result cannot show "
                "how much it depends on that choice.",
                [
                    "Add a contamination sensitivity analysis, or analyse by "
                    "assigned condition (ITT)."
                ],
            )
        )
    return warnings
