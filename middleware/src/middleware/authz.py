"""The project-scoping choke point (FR-PLAT-1/2, Slice A)."""

from collections.abc import Callable
from enum import StrEnum

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware.auth import Identity, Verifier
from middleware.db import (
    IMPLICIT_PROJECT_ID,
    Membership,
    Project,
    SessionBlock,
    SessionOpen,
    Study,
)


class Role(StrEnum):
    """A membership role on a project (fr-plat.md §2)."""

    OWNER = "owner"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


ROLE_RANK: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.RESEARCHER: 1,
    Role.OWNER: 2,
}


ROLES: frozenset[str] = frozenset(r.value for r in Role)


CAPABILITIES: dict[str, Role] = {
    "view": Role.VIEWER,
    "contribute": Role.RESEARCHER,
    "apply_draft": Role.RESEARCHER,
    "run_recipe": Role.RESEARCHER,
    "mint_token": Role.RESEARCHER,
    "toggle_capture": Role.RESEARCHER,
    "freeze": Role.OWNER,
    "invite_member": Role.RESEARCHER,
    "manage_members": Role.OWNER,
    "delete": Role.OWNER,
}


def has_role(their: Role | str | None, capability: str) -> bool:
    """True if ``their`` role satisfies ``capability`` (>= required)."""
    if their is None:
        return False
    role = their if isinstance(their, Role) else Role(str(their))
    required = CAPABILITIES[capability]
    return ROLE_RANK[role] >= ROLE_RANK[required]


def _forbidden(capability: str, role: str | None) -> HTTPException:
    """Plain-language 403 (F2.2)."""
    if role is None:
        body = (
            f"You're not a member of this project; {capability} needs at "
            "least the viewer role. Ask an owner for an invitation."
        )
    else:
        body = (
            f"You're a {role} on this project; {capability} needs a higher "
            "role. Ask an owner to change your role."
        )
    return HTTPException(status_code=403, detail=body)


def _membership_for(
    s: Session, identity_sub: str, project_id: str
) -> Membership | None:
    return s.scalar(
        select(Membership).where(
            Membership.project_id == project_id, Membership.identity_sub == identity_sub
        )
    )


def _project_by_slug(s: Session, slug: str) -> Project | None:
    return s.scalar(select(Project).where(Project.slug == slug))


def build_authz(
    session_factory: Callable[[], Session],
    verify: Verifier,
    loaded_study_id: Callable[[], str | None] = lambda: None,
) -> dict[str, Callable]:
    """Build the concrete authz dependencies as closures."""

    def resolve_identity(authorization: str = Header(default="")) -> Identity:
        """Auth + identity resolution in one place."""
        return verify(authorization)

    def _project_or_404(s: Session, slug: str) -> Project:
        proj = _project_by_slug(s, slug)
        if proj is None:
            raise HTTPException(status_code=404, detail="project not found")
        return proj

    def _demo_membership(identity: Identity, project: Project) -> Membership | None:
        """Viewer on the demo project, for anyone signed in."""
        from middleware.demo import DEMO_PROJECT_ID

        if project.id != DEMO_PROJECT_ID:
            return None
        return Membership(
            project_id=project.id,
            identity_sub=identity.sub,
            role=Role.VIEWER,
            invited_by="",
            joined_at="",
        )

    def _authorize(
        s: Session, identity: Identity, project: Project, capability: str
    ) -> Membership:
        m = _membership_for(s, identity.sub, project.id) or _demo_membership(
            identity, project
        )
        if m is None or not has_role(m.role, capability):
            raise _forbidden(capability, m.role if m else None)
        return m

    def require_project(capability: str) -> Callable:
        """Resolve ``(identity, :slug) -> Membership`` or 403/404."""

        def _dep(authorization: str = Header(default=""), slug: str = "") -> Membership:
            identity = verify(authorization)
            s = session_factory()
            try:
                project = _project_or_404(s, slug)
                return _authorize(s, identity, project, capability)
            finally:
                s.close()

        _dep.__authz_capability__ = capability
        return _dep

    def _authorize_study(
        s: Session, identity: Identity, study_id: str, capability: str
    ) -> Membership:
        """``study_id -> studies.project_id -> membership``, or 403/404."""
        study = s.scalar(select(Study).where(Study.id == study_id))
        if study is None:
            if loaded_study_id() is None and identity.mode != "clerk":
                implicit = _membership_for(s, identity.sub, IMPLICIT_PROJECT_ID)
                if implicit is not None and has_role(implicit.role, capability):
                    return implicit
            raise HTTPException(status_code=404, detail=f"unknown study {study_id!r}")
        project = s.scalar(select(Project).where(Project.id == study.project_id))
        if project is None:
            raise HTTPException(status_code=404, detail=f"unknown study {study_id!r}")
        return _authorize(s, identity, project, capability)

    def require_project_for_study(capability: str) -> Callable:
        """The study-keyed twin for the ``/studies/{study_id}/...`` routes."""

        def _dep(
            authorization: str = Header(default=""), study_id: str = ""
        ) -> Membership:
            identity = verify(authorization)
            s = session_factory()
            try:
                return _authorize_study(s, identity, study_id, capability)
            finally:
                s.close()

        _dep.__authz_capability__ = capability
        return _dep

    def require_project_for_session(capability: str) -> Callable:
        """The session-keyed twin, for ``/sessions/{session_id}/...`` routes."""

        def _dep(
            authorization: str = Header(default=""), session_id: str = ""
        ) -> Membership:
            identity = verify(authorization)
            s = session_factory()
            try:
                study_id = s.scalar(
                    select(SessionOpen.study_id).where(
                        SessionOpen.session_id == session_id
                    )
                ) or s.scalar(
                    select(SessionBlock.study_id).where(
                        SessionBlock.session_id == session_id
                    )
                )
                if study_id is None:
                    if identity.mode == "clerk":
                        raise HTTPException(
                            status_code=404, detail=f"unknown session {session_id!r}"
                        )
                    study_id = loaded_study_id() or ""
                return _authorize_study(s, identity, study_id, capability)
            finally:
                s.close()

        _dep.__authz_capability__ = capability
        return _dep

    def current_membership(
        authorization: str = Header(default=""), slug: str = ""
    ) -> Membership | None:
        """
        The viewer+ gate that also exposes the membership to the route (for UI-only role
        reflection via RoleGate).
        """
        identity = verify(authorization)
        s = session_factory()
        try:
            project = _project_by_slug(s, slug)
            if project is None:
                return None
            return _membership_for(s, identity.sub, project.id)
        finally:
            s.close()

    return {
        "resolve_identity": resolve_identity,
        "require_project": require_project,
        "require_project_for_study": require_project_for_study,
        "require_project_for_session": require_project_for_session,
        "current_membership": current_membership,
    }


__all__ = [
    "CAPABILITIES",
    "ROLES",
    "ROLE_RANK",
    "Role",
    "build_authz",
    "has_role",
]
