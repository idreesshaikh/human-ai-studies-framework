"""Member-invitation email delivery (FR-PLAT-3, D40).

Sends via Resend's REST API over stdlib ``urllib`` — no SDK, matching the
no-dependency posture of the LLM and GitHub clients. Everything here is
**best-effort and key-gated**: with no ``RESEND_API_KEY`` the platform
degrades to the copy-link flow, and a send failure never propagates (the
invitation record and its link are the source of truth; email is a courtesy).
"""

from __future__ import annotations

import html
import json
import logging
import urllib.request

log = logging.getLogger("middleware.mailer")

RESEND_ENDPOINT = "https://api.resend.com/emails"


def invite_enabled(api_key: str | None) -> bool:
    """Whether email delivery is configured. Absent → copy-link fallback."""
    return bool(api_key)


def _accept_url(token: str, base_url: str | None) -> str:
    path = f"/invitations/{token}"
    if not base_url:
        return path
    return f"{base_url.rstrip('/')}{path}"


def _body_html(project_name: str, role: str, accept_url: str) -> str:
    # Deliberately plain — one line of context, one clear action. Every
    # interpolated value is HTML-escaped: the project name is user-controlled,
    # so an unescaped name would inject markup into the invite email. quote=True
    # keeps a stray quote in the URL from breaking out of the href attribute.
    p = html.escape(project_name)
    r = html.escape(role)
    u = html.escape(accept_url, quote=True)
    return (
        f'<p>You’ve been invited to join <strong>{p}</strong> '
        f'on PHOENIX as <strong>{r}</strong>.</p>'
        f'<p><a href="{u}">Accept the invitation</a></p>'
        f"<p>The link works once and expires in 7 days.</p>"
    )


def send_invitation(
    *,
    api_key: str | None,
    from_email: str,
    to_email: str,
    project_name: str,
    role: str,
    token: str,
    base_url: str | None,
    post=None,
) -> bool:
    """Email an invitation. Returns True if a send was attempted and accepted,
    False if delivery is unconfigured or failed. Never raises — the caller's
    invitation record stands regardless. ``post`` is injectable for tests."""
    if not invite_enabled(api_key):
        return False
    accept_url = _accept_url(token, base_url)
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": f"You're invited to {project_name} on PHOENIX",
        "html": _body_html(project_name, role, accept_url),
    }
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
        return True
    except Exception as exc:  # noqa: BLE001 - best-effort; log once, never block
        log.warning("invitation email to %s not sent: %s", to_email, exc)
        return False


def _post_json(url: str, body: dict, headers: dict[str, str]) -> dict:
    """POST JSON, return parsed JSON. The one network seam (mirrors
    assistant._post_json) so tests can inject a fake sender."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed host
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}
