"""The project-scoping choke point (FR-PLAT-1/2, Slice A).

One seam, testable by construction (the FR-ETH-4 pattern). Every
project-scoped router depends on :func:`require_project` (or the
study-keyed twin :func:`require_project_for_study`); no route re-implements
the check. Adding a capability without a test is impossible by
construction - the matrix is a dict that tests iterate.

Two things live here:

1. **Pure data** - :class:`Role`, :data:`ROLE_RANK`, :data:`CAPABILITIES`,
   :func:`has_role`. These mirror ``fr-plat.md`` §2 exactly and carry no
   FastAPI/DB state, so tests import them directly to drive the
   parameterized (route x role) matrix (F2.1) and the route-audit (F2.3).
2. **A factory builder** - :func:`build_authz`, called once from
   ``create_app`` with the session factory + verifier, returning the
   concrete ``require_project`` / ``require_project_for_study`` /
   ``resolve_identity`` dependencies as closures (mirroring how
   ``view_auth`` is wired today).

The permission matrix is enforced **server-side** here; the UI merely
reflects it (FR-PLAT-2 F2.3: "no permission check exists only in the
frontend"). A 403 body is a plain-language sentence (F2.2). 404 before 403
on cross-project access - a non-member probing another project's study by
id learns nothing (FR-PLAT-1 fit: "cross-project reads provably impossible").
"""

from collections.abc import Callable
from enum import StrEnum

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware.auth import Identity, Verifier
from middleware.db import IMPLICIT_PROJECT_ID, Membership, Project, Study


class Role(StrEnum):
    """A membership role on a project (fr-plat.md §2)."""

    OWNER = "owner"
    RESEARCHER = "researcher"
    VIEWER = "viewer"


#: Role rank for ">=" capability checks. A role satisfies a capability when
#: ``ROLE_RANK[their_role] >= ROLE_RANK[required_role]`` - one comparison
#: covers the whole matrix.
ROLE_RANK: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.RESEARCHER: 1,
    Role.OWNER: 2,
}


#: The valid role strings, for request-body validation on the role-setting
#: endpoints (change_role, create_invitation). A set so membership checks
#: read naturally: ``role not in ROLES``.
ROLES: frozenset[str] = frozenset(r.value for r in Role)


#: The permission matrix from ``fr-plat.md`` §2 as DATA. The capability key
#: is the server-side vocabulary every project-scoped route names; the value
#: is the *minimum* role that may exercise it. Tests iterate this dict to
#: generate the (route x role) matrix - so adding a capability without tests
#: is impossible by construction (F2.1 driver).
CAPABILITIES: dict[str, Role] = {
    # View studies, reports, conversations.
    "view": Role.VIEWER,
    # Contribute conversation turns / design moves.
    "contribute": Role.RESEARCHER,
    # Apply compiled drafts (pre-freeze).
    "apply_draft": Role.RESEARCHER,
    # Run mining jobs; upload gate artifacts.
    "run_recipe": Role.RESEARCHER,
    # Mint/revoke enrollment (pairing) tokens for a study.
    "mint_token": Role.RESEARCHER,
    # Toggle individual capture metrics (Phase 20, FR-DASH-11).
    "toggle_capture": Role.RESEARCHER,
    # Freeze protocol; approve post-ethics amendments.
    "freeze": Role.OWNER,
    # Invite a colleague to the project (D40): researchers+ can invite peers,
    # separate from managing roles/removals. The invited person still lands
    # with a pre-assigned role, and only owners can grant the owner role.
    "invite_member": Role.RESEARCHER,
    # Manage members, roles, invitations (change roles, remove, revoke).
    "manage_members": Role.OWNER,
    # Delete study / project.
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
    """Plain-language 403 (F2.2). Roles are facts - the message names the
    gap without hedging."""
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
    """Build the concrete authz dependencies as closures.

    Called once from ``create_app`` (mirroring the ``view_auth`` wiring at
    app.py:246-249). Returns a dict of named dependencies so the routes
    read ``Depends(authz["require_project"])("view"))``-style - greppable,
    one choke point.
    """

    def resolve_identity(authorization: str = Header(default="")) -> Identity:
        """Auth + identity resolution in one place. Every project-scoped
        route starts here; the verifier raises 401/503 on rejection."""
        return verify(authorization)

    def _project_or_404(s: Session, slug: str) -> Project:
        proj = _project_by_slug(s, slug)
        if proj is None:
            # 404 before 403: a non-member probing slug names learns nothing
            # about whether the project exists (FR-PLAT-1).
            raise HTTPException(status_code=404, detail="project not found")
        return proj

    def _authorize(
        s: Session, identity: Identity, project: Project, capability: str
    ) -> Membership:
        m = _membership_for(s, identity.sub, project.id)
        if m is None or not has_role(m.role, capability):
            raise _forbidden(capability, m.role if m else None)
        return m

    def require_project(capability: str) -> Callable:
        """Resolve ``(identity, :slug) -> Membership`` or 403/404.

        Reads ``Authorization`` and the ``slug`` path param. Usage in a
        route: ``Depends(require_project("view"))`` where ``slug`` is a
        path parameter named exactly ``slug``.
        """

        def _dep(authorization: str = Header(default=""), slug: str = "") -> Membership:
            identity = verify(authorization)
            s = session_factory()
            try:
                project = _project_or_404(s, slug)
                return _authorize(s, identity, project, capability)
            finally:
                s.close()

        return _dep

    def require_project_for_study(capability: str) -> Callable:
        """The study-keyed twin for the ``/studies/{study_id}/...`` routes.
        Resolves ``study_id -> studies.project_id -> membership``. Self-hosted
        single-facilitator deployments resolve through the implicit project
        (FR-PLAT-5)."""

        def _dep(
            authorization: str = Header(default=""), study_id: str = ""
        ) -> Membership:
            identity = verify(authorization)
            s = session_factory()
            try:
                study = s.scalar(select(Study).where(Study.id == study_id))
                if study is None:
                    # When a protocol is loaded, its study row exists, so an
                    # unknown id 404s exactly as the pre- check_study_id
                    # did. When no protocol is loaded, the middleware is a
                    # permissive sink (v1 accept-all) and single-facilitator
                    # modes have no cross-project probing to defend against -
                    # resolve to the implicit project's membership. Clerk
                    # (multi-tenant) always 404s an unknown study.
                    if loaded_study_id() is None and identity.mode != "clerk":
                        implicit = _membership_for(s, identity.sub, IMPLICIT_PROJECT_ID)
                        if implicit is not None and has_role(implicit.role, capability):
                            return implicit
                    raise HTTPException(
                        status_code=404, detail=f"unknown study {study_id!r}"
                    )
                project = s.scalar(
                    select(Project).where(Project.id == study.project_id)
                )
                if project is None:
                    raise HTTPException(
                        status_code=404, detail=f"unknown study {study_id!r}"
                    )
                return _authorize(s, identity, project, capability)
            finally:
                s.close()

        return _dep

    def current_membership(
        authorization: str = Header(default=""), slug: str = ""
    ) -> Membership | None:
        """The viewer+ gate that also exposes the membership to the route
        (for UI-only role reflection via RoleGate). None when the caller is
        not a member (routes that want strict membership use
        ``require_project`` instead)."""
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
