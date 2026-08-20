"""Member-invitation email delivery (FR-PLAT-3, D40)."""

from __future__ import annotations

import html
import json
import logging
import urllib.error
import urllib.request
from contextlib import suppress
from email.utils import formataddr, parseaddr

log = logging.getLogger("middleware.mailer")

RESEND_ENDPOINT = "https://api.resend.com/emails"


def invite_enabled(api_key: str | None) -> bool:
    """Whether email delivery is configured."""
    return bool(api_key)


def _accept_url(token: str, base_url: str | None) -> str:
    path = f"/invitations/{token}"
    if not base_url:
        return path
    return f"{base_url.rstrip('/')}{path}"


def _body_html(project_name: str, role: str, accept_url: str) -> str:
    # Deliberately plain — one line of context, one clear action.
    p = html.escape(project_name)
    r = html.escape(role)
    u = html.escape(accept_url, quote=True)
    return (
        f'<p>You’ve been invited to join <strong>{p}</strong> '
        f'on PHOENIX as <strong>{r}</strong>.</p>'
        f'<p><a href="{u}">Accept the invitation</a></p>'
        f"<p>The link works once and expires in 7 days.</p>"
    )


def _from_and_reply(from_email: str, inviter: str) -> tuple[str, str | None]:
    """Make the invite read as coming from the person who sent it, without spoofing."""
    name, addr = parseaddr(from_email)
    inviter = inviter.strip()
    if not inviter or not addr:
        return from_email, None
    brand = name or "PHOENIX"
    # If the inviter identity is itself an email, don't repeat it in the display name;
    # use it as Reply-To so replies reach the real person.
    reply_to = inviter if "@" in inviter and " " not in inviter else None
    display = brand if reply_to else f"{inviter} via {brand}"
    return formataddr((display, addr)), reply_to


def send_invitation(
    *,
    api_key: str | None,
    from_email: str,
    to_email: str,
    project_name: str,
    role: str,
    token: str,
    base_url: str | None,
    inviter: str = "",
    post=None,
) -> tuple[bool, str]:
    """Email an invitation."""
    if not invite_enabled(api_key):
        return False, (
            "Email delivery isn't configured (no RESEND_API_KEY). "
            "Share the copy link instead."
        )
    accept_url = _accept_url(token, base_url)
    from_header, reply_to = _from_and_reply(from_email, inviter)
    payload = {
        "from": from_header,
        "to": [to_email],
        "subject": f"You're invited to {project_name} on PHOENIX",
        "html": _body_html(project_name, role, accept_url),
    }
    if reply_to:
        payload["reply_to"] = reply_to
    sender = post or _post_json
    try:
        sender(
            RESEND_ENDPOINT,
            payload,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        return True, "Sent."
    except urllib.error.HTTPError as exc:
        detail = _resend_error_detail(exc)
        reason = f"The email provider rejected the send ({exc.code}): {detail}"
        log.warning("invitation email to %s not sent: %s", to_email, reason)
        return False, reason
    except Exception as exc:  # noqa: BLE001 - best-effort; log once, never block
        reason = f"Couldn't reach the email provider: {exc}"
        log.warning("invitation email to %s not sent: %s", to_email, reason)
        return False, reason


def _resend_error_detail(exc: urllib.error.HTTPError) -> str:
    """
    Pull Resend's ``message`` out of an HTTP error body, falling back to the raw text
    (then the reason phrase) when it isn't the expected JSON shape.
    """
    try:
        raw = exc.read().decode("utf-8")
    except Exception:  # noqa: BLE001 - diagnostics only, never mask the original
        return exc.reason or "unknown error"
    with suppress(Exception):
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return str(parsed.get("message") or parsed.get("error") or raw)
    return raw or (exc.reason or "unknown error")


def _post_json(url: str, body: dict, headers: dict[str, str]) -> dict:
    """
    POST JSON, return parsed JSON. The one network seam (mirrors assistant._post_json)
    so tests can inject a fake sender.
    """
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}
