"""
The study folder a minted link opens (issue 36).

A researcher names the folder one of two ways: a path that exists on the
participants' machines, or a zip of the folder the extension downloads and
unpacks. This module only validates; the routes own storage and auth.
"""

from __future__ import annotations

import io
import re
import stat
import zipfile

MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_UNPACKED_BYTES = 200 * 1024 * 1024
MAX_ENTRIES = 5000

_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


class WorkspaceError(ValueError):
    """The submitted folder is not something a participant's machine can open."""


def validate_path(raw: str) -> str:
    """An absolute path, ``~/`` path or ``file://`` URI; anything else is refused."""
    value = (raw or "").strip()
    if not value:
        raise WorkspaceError("the folder path is empty")
    if re.match(r"^https?://", value, re.I) or value.endswith(
        (".zip", ".tar", ".tar.gz", ".tgz")
    ):
        raise WorkspaceError(
            "a repository URL or archive file is not a folder path; upload a zip "
            "of the folder instead"
        )
    if not (
        value.startswith(("file://", "/", "~/"))
        or _WINDOWS_ABSOLUTE.match(value)
    ):
        raise WorkspaceError(
            "use an absolute path (/home/..., C:\\...), ~/..., or a file:// URI"
        )
    if ".." in re.split(r"[\\/]", value):
        raise WorkspaceError("the folder path may not contain '..'")
    return value


def validate_archive(data: bytes) -> int:
    """Check an uploaded zip is safe to unpack; return its file count."""
    if not data:
        raise WorkspaceError("the uploaded file is empty")
    if len(data) > MAX_ARCHIVE_BYTES:
        raise WorkspaceError(
            f"the zip is larger than {MAX_ARCHIVE_BYTES // (1024 * 1024)} MB"
        )
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise WorkspaceError("the uploaded file is not a valid zip") from exc
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise WorkspaceError(f"the zip has more than {MAX_ENTRIES} entries")
    total = 0
    files = 0
    for info in infos:
        name = info.filename
        parts = re.split(r"[\\/]", name)
        if (
            name.startswith(("/", "\\"))
            or _WINDOWS_ABSOLUTE.match(name)
            or ".." in parts
        ):
            raise WorkspaceError(f"the zip contains an unsafe path: {name!r}")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise WorkspaceError(f"the zip contains a symbolic link: {name!r}")
        total += info.file_size
        files += 0 if info.is_dir() else 1
    if total > MAX_UNPACKED_BYTES:
        raise WorkspaceError(
            f"the zip unpacks to more than {MAX_UNPACKED_BYTES // (1024 * 1024)} MB"
        )
    if files == 0:
        raise WorkspaceError("the zip contains no files")
    if zf.testzip() is not None:
        raise WorkspaceError("the zip is corrupt")
    return files
