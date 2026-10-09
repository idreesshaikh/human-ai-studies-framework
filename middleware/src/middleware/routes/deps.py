"""Collaborators shared by route modules, built once in create_app."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from middleware.settings import Settings


@dataclass(frozen=True)
class ApiDeps:
    """Route modules read these collaborators and never import middleware.app."""

    settings: Settings
    session_factory: Callable[[], Any]
    check: Any
    protocol_loaded: Callable[[], bool]
    web_index: Path
    web_hash: Any
    db: Callable[..., Any]
    now: Callable[[], str]
    resolve_credential: Callable[..., Any]
    session_scope: Callable[..., Any]
    authz: dict[str, Callable]
    view_auth: Callable[..., Any]
    resolve_study_protocol: Callable[..., Any]
    joined_rows: Callable[..., Any]
    conversation_moves: Callable[..., Any]
    clock: Callable[[], datetime]
    export_elicitation: Callable[..., Any]
    conversation_seq: Callable[..., Any]
    adopt_corpus_paper: Callable[..., Any]
