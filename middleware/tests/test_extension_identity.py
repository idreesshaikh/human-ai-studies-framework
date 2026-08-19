"""The platform's VS Code deep link must name the extension that exists.

VS Code resolves a ``vscode://<publisher>.<name>/...`` URI purely by string
match against installed extensions. A wrong identity does not error - the URI
is simply claimed by nobody and the participant sees the click do nothing.
The platform shipped exactly that failure (``hpi-research.cognitive-overlay``,
an identity never published under any name), and nothing caught it because the
literal lived in a React component with no reader on the other side.

So the two ends are pinned together here: ``extension/package.json`` is the
document of record for the extension's identity, and ``platform/src/lib/
extension.ts`` is the single place the platform states it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXTENSION_MANIFEST = REPO / "extension" / "package.json"
PLATFORM_CONSTANTS = REPO / "platform" / "src" / "lib" / "extension.ts"


def _manifest() -> dict:
    return json.loads(EXTENSION_MANIFEST.read_text())


def _constant(name: str) -> str:
    """The value of an exported string const in the platform module."""
    source = PLATFORM_CONSTANTS.read_text()
    match = re.search(
        rf'export const {name}\s*=\s*\n?\s*"([^"]+)"', source
    )
    assert match, f"{name} is not exported from {PLATFORM_CONSTANTS.name}"
    return match.group(1)


def test_platform_deep_link_names_the_real_extension() -> None:
    manifest = _manifest()
    expected = f"{manifest['publisher']}.{manifest['name']}"
    assert _constant("EXTENSION_ID") == expected, (
        "the platform's deep-link identity has drifted from the extension "
        "manifest - the vscode:// link will silently resolve to nothing"
    )


def test_no_component_hardcodes_its_own_extension_identity() -> None:
    """Every ``vscode://`` URI must be built from the shared constant."""
    platform_src = REPO / "platform" / "src"
    offenders = [
        path.relative_to(REPO)
        for path in platform_src.rglob("*.ts*")
        if path != PLATFORM_CONSTANTS and "vscode://" in path.read_text()
    ]
    assert not offenders, f"build the deep link via vscodeDeepLink(): {offenders}"


def test_releases_url_points_at_the_extension_repository() -> None:
    """TERN is installed from a GitHub release, never the Marketplace, so the
    install link has to track the repository the extension declares."""
    repo_url = _manifest()["repository"]["url"].removesuffix(".git")
    assert _constant("EXTENSION_RELEASES_URL").startswith(repo_url), (
        "the install link does not point at the extension's own repository"
    )
