"""Content-policy choke point (FR-AGENT-5)."""

from agent_capture.redact import (
    POLICY_DESCRIPTIONS,
    apply_policy,
    normalize_policy,
    policy_description,
    redact_text,
)

SECRET = 'token = "sk-live-abcdef"; def transfer(amount): return amount'


def test_metadata_only_strips_everything():
    assert apply_policy(SECRET, "metadata-only") is None
    assert apply_policy("anything", "metadata-only") is None


def test_full_passes_through():
    assert apply_policy(SECRET, "full") == SECRET


def test_redacted_masks_literals_and_long_identifiers():
    out = redact_text(SECRET)
    assert "sk-live-abcdef" not in out
    assert "transfer" not in out  # >= 4 chars identifier masked
    assert "amount" not in out
    # Short tokens and structure survive so shape is analyzable.
    assert "=" in out and "(" in out


def test_unknown_policy_collapses_to_safe_default():
    # A misconfiguration must never *widen* capture.
    assert normalize_policy("full-send") == "metadata-only"
    assert apply_policy(SECRET, None) is None


def test_none_text_yields_none_at_any_policy():
    assert apply_policy(None, "full") is None


def test_descriptions_exist_for_the_consent_form():
    # The consent-form generator interpolates these verbatim.
    for policy in ("metadata-only", "redacted", "full"):
        assert policy_description(policy) == POLICY_DESCRIPTIONS[policy]
        assert len(policy_description(policy)) > 20
