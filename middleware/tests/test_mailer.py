"""
The invitation mailer surfaces *why* a send didn't happen instead of swallowing it
silently (the old bug: a good key with an unverified sender domain failed invisibly).
"""

import io
import urllib.error

from middleware import mailer

_KW = {
    "from_email": "PHOENIX <invites@example.test>",
    "to_email": "colleague@lab.example",
    "project_name": "Trust study",
    "role": "viewer",
    "token": "tok123",
    "base_url": "https://app.example.test",
}


def test_unconfigured_returns_reason():
    sent, reason = mailer.send_invitation(api_key=None, **_KW)
    assert sent is False
    assert "RESEND_API_KEY" in reason


def test_http_error_surfaces_provider_message():
    def boom(url, body, headers):
        raise urllib.error.HTTPError(
            url,
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"message": "The domain is not verified."}'),
        )

    sent, reason = mailer.send_invitation(api_key="re_test", post=boom, **_KW)
    assert sent is False
    assert "403" in reason
    assert "domain is not verified" in reason


def test_success_returns_true():
    def ok(url, body, headers):
        assert headers["Authorization"] == "Bearer re_test"
        return {"id": "email_1"}

    sent, reason = mailer.send_invitation(api_key="re_test", post=ok, **_KW)
    assert sent is True
    assert reason


def test_inviter_name_shows_in_from_without_spoofing():
    seen = {}

    def ok(url, body, headers):
        seen.update(body)
        return {"id": "email_1"}

    sent, _ = mailer.send_invitation(
        api_key="re_test", post=ok, inviter="Ada Lovelace", **_KW
    )
    assert sent is True
    assert seen["from"] == "Ada Lovelace via PHOENIX <invites@example.test>"
    assert "reply_to" not in seen


def test_inviter_email_sets_reply_to():
    seen = {}

    def ok(url, body, headers):
        seen.update(body)
        return {"id": "email_1"}

    mailer.send_invitation(
        api_key="re_test", post=ok, inviter="ada@lab.example", **_KW
    )
    assert seen["reply_to"] == "ada@lab.example"
    assert seen["from"] == "PHOENIX <invites@example.test>"
