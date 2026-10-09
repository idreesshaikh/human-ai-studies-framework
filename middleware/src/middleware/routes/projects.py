"""Projects API routes."""

import copy
import logging
import re
import secrets
from datetime import datetime

import yaml
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)
from sqlalchemy import func, select, union
from sqlalchemy.orm import Session

from middleware import (
    auth,
    authz,
)
from middleware.db import (
    ApprovalEvent,
    Compilation,
    ConversationTurn,
    DesignMoveRow,
    EnrollmentToken,
    Event,
    EvidenceMapRow,
    Invitation,
    Membership,
    MetricRow,
    Paper,
    PaperEdge,
    PaperLink,
    Project,
    ProtocolDraftRow,
    RecipeRun,
    SessionAnnotation,
    SessionBlock,
    SessionOpen,
    StoredFile,
    Study,
    StudyAuditRecord,
    StudyPlan,
    StudyWorkspace,
    UserProfile,
)
from middleware.route_helpers import (
    _slug_from_text,
)
from middleware.routes.deps import ApiDeps

log = logging.getLogger("middleware.app")


def register(app: FastAPI, deps: ApiDeps):
    @app.post("/projects", dependencies=[Depends(deps.authz["resolve_identity"])])
    def create_project(
        body: dict,
        identity: auth.Identity = Depends(deps.authz["resolve_identity"]),
        s: Session = Depends(deps.db),
    ) -> dict:
        """Create a new project (FR-PLAT-1), or return existing implicit project."""
        name = str(body.get("name", "")).strip()
        if not name:
            raise HTTPException(400, "name is required")
        if len(name) > 80:
            raise HTTPException(400, "Project names must be 80 characters or fewer.")

        # Phase 6: Implicit personal projects. If the caller creates a project named
        # "Personal", check if they already have one  -  if so, return it (reusable).
        if name == "Personal":
            existing = s.scalar(
                select(Project)
                .join(Membership)
                .where(
                    (Project.name == "Personal")
                    & (Membership.identity_sub == identity.sub)
                    & (Membership.role == "owner")
                )
            )
            if existing:
                study_count = (
                    s.scalar(
                        select(func.count())
                        .select_from(Study)
                        .where(Study.project_id == existing.id)
                    )
                    or 0
                )
                return {
                    "id": existing.id,
                    "slug": existing.slug,
                    "name": existing.name,
                    "role": "owner",
                    "createdAt": existing.created_at,
                    "studyCount": study_count,
                }

        chosen = str(body.get("slug", "")).strip()
        if len(chosen) > 50 or (chosen and not re.fullmatch(r"[a-z0-9-]+", chosen)):
            raise HTTPException(
                400, "Use a slug of up to 50 lowercase letters, numbers or hyphens."
            )
        slug = chosen
        if not slug:
            slug = _slug_from_text(name, 50)
        if not slug:
            slug = secrets.token_hex(4)
        if chosen:
            if s.scalar(select(Project).where(Project.slug == chosen)) is not None:
                raise HTTPException(409, f"slug {chosen!r} is taken")
        else:
            base, suffix = slug, 1
            while s.scalar(select(Project).where(Project.slug == slug)) is not None:
                suffix += 1
                slug = f"{base}-{suffix}"
        pid = secrets.token_hex(8)
        created = deps.now()
        s.add(
            Project(
                id=pid,
                name=name,
                slug=slug,
                created_by=identity.sub,
                created_at=created,
            )
        )
        s.flush()
        s.add(
            Membership(
                project_id=pid,
                identity_sub=identity.sub,
                role="owner",
                invited_by="",
                joined_at=deps.now(),
            )
        )
        s.flush()
        # Returning a partial row here is what made the list and the create response two
        # different types wearing one name.
        return {
            "id": pid,
            "slug": slug,
            "name": name,
            "role": "owner",
            "createdAt": created,
            "studyCount": 0,
        }

    @app.get("/projects", dependencies=[Depends(deps.authz["resolve_identity"])])
    def list_projects(
        identity: auth.Identity = Depends(deps.authz["resolve_identity"]),
        s: Session = Depends(deps.db),
    ) -> list[dict]:
        """
        My project memberships (FR-PLAT-2), each carrying the shape of what is inside it
        (FR-PLAT-1): how many studies it holds.
        """
        rows = s.execute(
            select(Project, Membership.role)
            .join(Membership, Membership.project_id == Project.id)
            .where(Membership.identity_sub == identity.sub)
            .order_by(Project.created_at.desc())
        ).all()
        counts: dict[str, int] = {}
        if rows:
            for project_id, count in s.execute(
                select(Study.project_id, func.count())
                .where(Study.project_id.in_([proj.id for proj, _ in rows]))
                .group_by(Study.project_id)
            ):
                counts[project_id] = count
        return [
            {
                "id": p.id,
                "slug": p.slug,
                "name": p.name,
                "role": role,
                "createdAt": p.created_at,
                "studyCount": counts.get(p.id, 0),
            }
            for p, role in rows
        ]

    @app.get(
        "/projects/{slug}",
        dependencies=[Depends(deps.authz["require_project"]("view"))],
    )
    def project_home(slug: str, s: Session = Depends(deps.db)) -> dict:
        """Project home payload: project info, studies, members preview."""
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        studies = [
            {
                "id": st.id,
                "hasProtocol": deps.resolve_study_protocol(s, st.id) is not None,
            }
            for st in s.scalars(select(Study).where(Study.project_id == proj.id))
        ]
        member_rows = list(
            s.scalars(select(Membership).where(Membership.project_id == proj.id))
        )
        members = [
            {
                "identitySub": m.identity_sub,
                "role": m.role,
            }
            for m in member_rows
        ]
        invitations = [
            {
                "id": inv.id,
                "role": inv.role,
                "createdAt": inv.created_at,
                "expiresAt": inv.expires_at,
            }
            for inv in s.scalars(
                select(Invitation).where(Invitation.project_id == proj.id)
            )
        ]
        return {
            "id": proj.id,
            "slug": proj.slug,
            "name": proj.name,
            "studies": studies,
            "members": members,
            "invitations": invitations,
        }

    @app.post(
        "/projects/{slug}/studies",
        dependencies=[Depends(deps.authz["require_project"]("contribute"))],
    )
    def create_study(slug: str, body: dict, s: Session = Depends(deps.db)) -> dict:
        """
        Start a new study in this project (FR-PLAT-1 continued): the design conversation
        needs a study row to attach its moves/drafts to before it can run
        -  this is that row, empty and pre-design, ready for the researcher to talk it
        into existence.
        """
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        name = str(body.get("name", "")).strip()
        base = _slug_from_text(name, 40) if name else ""
        if len(name) > 120:
            raise HTTPException(400, "Study names must be 120 characters or fewer.")
        if not base:
            base = "study"
        study_id = base
        suffix = 1
        while s.scalar(select(Study).where(Study.id == study_id)) is not None:
            suffix += 1
            study_id = f"{base}-{suffix}"
        seed = body.get("protocol")
        if seed is not None and (
            not isinstance(seed, dict)
            or not isinstance(seed.get("study"), dict)
            or not isinstance(seed.get("researchQuestions"), list)
        ):
            raise HTTPException(
                422,
                "protocol must be a compiled protocol: an object with "
                "study and researchQuestions",
            )
        s.add(
            Study(
                id=study_id,
                project_id=proj.id,
                protocol_version="",
                data_path="",
            )
        )
        if seed is not None:
            # A template carries an archetype's example id/title so it can be
            # instantiated on its own. Once it becomes this study's draft those
            # values must belong to the study the researcher just named. Leaving
            # them untouched made a study called “Junior vs senior” calculate
            # against a generic template identity and exposed its defaults as
            # though they were this study's plan.
            seed = copy.deepcopy(seed)
            seed.setdefault("study", {})["id"] = study_id
            seed["study"]["title"] = name
            s.add(
                ProtocolDraftRow(
                    study_id=study_id,
                    yaml=yaml.safe_dump(
                        seed, sort_keys=False, default_flow_style=False
                    ),
                    compilation_id="",
                    updated_at=deps.now(),
                )
            )
        s.flush()
        return {"id": study_id}

    # The corpus study is never a target (it isn't a project study).
    _STUDY_SCOPED = (
        StoredFile,
        Paper,
        PaperEdge,
        PaperLink,
        RecipeRun,
        EnrollmentToken,
        DesignMoveRow,
        ConversationTurn,
        ApprovalEvent,
        Compilation,
        ProtocolDraftRow,
        EvidenceMapRow,
        SessionBlock,
        SessionOpen,
        SessionAnnotation,
        StudyPlan,
        StudyAuditRecord,
        StudyWorkspace,
    )

    def _delete_study_scoped_rows(s: Session, study_id: str) -> None:
        # Capture is keyed by session, not study. Resolve ownership before deleting
        # its mappings; never infer it from a participant or a name prefix.
        owned = union(
            select(SessionOpen.session_id).where(SessionOpen.study_id == study_id),
            select(SessionBlock.session_id).where(SessionBlock.study_id == study_id),
        )
        shared = union(
            select(SessionOpen.session_id).where(SessionOpen.study_id != study_id),
            select(SessionBlock.session_id).where(SessionBlock.study_id != study_id),
        )
        for model in (Event, MetricRow):
            s.execute(
                model.__table__.delete().where(
                    model.session_id.in_(owned), model.session_id.not_in(shared)
                )
            )
        for model in _STUDY_SCOPED:
            s.execute(model.__table__.delete().where(model.study_id == study_id))

    @app.delete(
        "/studies/{study_id}",
        dependencies=[Depends(deps.authz["require_project_for_study"]("delete"))],
    )
    def delete_study(study_id: str, s: Session = Depends(deps.db)) -> dict:
        """
        Delete a study and everything scoped to it (FR-PLAT-1): its conversation, design
        moves, drafts, papers, enrollment, and mining records.
        """
        study = s.get(Study, study_id)
        if study is None:
            raise HTTPException(404, "study not found")
        _delete_study_scoped_rows(s, study_id)
        s.delete(study)
        s.flush()
        return {"deleted": study_id}

    @app.patch(
        "/projects/{slug}",
        dependencies=[Depends(deps.authz["require_project"]("manage_members"))],
    )
    def rename_project(slug: str, body: dict, s: Session = Depends(deps.db)) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        name = str(body.get("name", "")).strip()
        if not name:
            raise HTTPException(400, "name is required")
        if len(name) > 80:
            raise HTTPException(400, "Project names must be 80 characters or fewer.")
        proj.name = name
        s.flush()
        return {"id": proj.id, "slug": proj.slug, "name": proj.name}

    @app.delete(
        "/projects/{slug}",
        dependencies=[Depends(deps.authz["require_project"]("delete"))],
    )
    def delete_project(slug: str, body: dict, s: Session = Depends(deps.db)) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        confirm = str(body.get("confirm", "")).strip()
        if confirm != "DELETE":
            raise HTTPException(400, "type DELETE to confirm deletion")
        study_ids = list(s.scalars(select(Study.id).where(Study.project_id == proj.id)))
        for study_id in study_ids:
            _delete_study_scoped_rows(s, study_id)
        s.execute(Study.__table__.delete().where(Study.project_id == proj.id))
        s.execute(Membership.__table__.delete().where(Membership.project_id == proj.id))
        s.execute(Invitation.__table__.delete().where(Invitation.project_id == proj.id))
        s.delete(proj)
        s.flush()
        return {"deleted": proj.slug}

    @app.get(
        "/projects/{slug}/members",
        dependencies=[Depends(deps.authz["require_project"]("view"))],
    )
    def list_members(slug: str, s: Session = Depends(deps.db)) -> list[dict]:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        return [
            {
                "identitySub": m.identity_sub,
                "role": m.role,
                "invitedBy": m.invited_by,
                "joinedAt": m.joined_at,
            }
            for m in s.scalars(
                select(Membership).where(Membership.project_id == proj.id)
            )
        ]

    @app.patch(
        "/projects/{slug}/members/{identity_sub}",
        dependencies=[Depends(deps.authz["require_project"]("manage_members"))],
    )
    def change_role(
        slug: str, identity_sub: str, body: dict, s: Session = Depends(deps.db)
    ) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        m = s.scalar(
            select(Membership).where(
                Membership.project_id == proj.id,
                Membership.identity_sub == identity_sub,
            )
        )
        if m is None:
            raise HTTPException(404, "member not found")
        new_role = str(body.get("role", "")).strip()
        if new_role not in authz.ROLES:
            raise HTTPException(400, "Choose owner, member or viewer as the role.")
        m.role = new_role
        s.flush()
        return {"identitySub": m.identity_sub, "role": m.role}

    @app.delete(
        "/projects/{slug}/members/{identity_sub}",
        dependencies=[Depends(deps.authz["require_project"]("manage_members"))],
    )
    def remove_member(
        slug: str, identity_sub: str, s: Session = Depends(deps.db)
    ) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        m = s.scalar(
            select(Membership).where(
                Membership.project_id == proj.id,
                Membership.identity_sub == identity_sub,
            )
        )
        if m is None:
            raise HTTPException(404, "member not found")
        if m.role == "owner":
            owner_count = s.scalar(
                select(func.count())
                .select_from(Membership)
                .where(Membership.project_id == proj.id, Membership.role == "owner")
            )
            if owner_count <= 1:
                raise HTTPException(
                    409, "can't remove the last owner. Transfer ownership first"
                )
        s.delete(m)
        s.flush()
        return {"removed": identity_sub}

    @app.post(
        "/projects/{slug}/invitations",
        dependencies=[Depends(deps.authz["require_project"]("invite_member"))],
    )
    def create_invitation(
        slug: str,
        body: dict,
        s: Session = Depends(deps.db),
        identity: auth.Identity = Depends(deps.authz["resolve_identity"]),
    ) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        role = str(body.get("role", "")).strip()
        if role not in authz.ROLES:
            raise HTTPException(400, "Choose owner or member as the role.")
        email = str(body.get("email", "")).strip()
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise HTTPException(400, "Enter a valid email address.")
        # A member can invite peers (D40), but only an owner can mint an owner invite  -
        # otherwise invite_member would be a backdoor to ownership.
        if role == authz.Role.OWNER.value:
            caller = s.scalar(
                select(Membership).where(
                    Membership.project_id == proj.id,
                    Membership.identity_sub == identity.sub,
                )
            )
            if caller is None or not authz.has_role(caller.role, "manage_members"):
                raise HTTPException(403, "only an owner can invite another owner")
        from datetime import timedelta as td

        now = deps.clock()
        expires = now + td(days=7)
        token = secrets.token_urlsafe(32)
        inv_id = secrets.token_hex(8)
        s.add(
            Invitation(
                id=inv_id,
                project_id=proj.id,
                role=role,
                token=token,
                created_at=now.isoformat(timespec="milliseconds"),
                expires_at=expires.isoformat(timespec="milliseconds"),
            )
        )
        s.flush()
        url = f"/invitations/{token}"
        return {
            "id": inv_id,
            "token": token,
            "url": url,
            "role": role,
            "createdAt": now.isoformat(timespec="milliseconds"),
            "expiresAt": expires.isoformat(timespec="milliseconds"),
        }

    @app.delete(
        "/projects/{slug}/invitations/{inv_id}",
        dependencies=[Depends(deps.authz["require_project"]("manage_members"))],
    )
    def revoke_invitation(
        slug: str, inv_id: str, s: Session = Depends(deps.db)
    ) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        inv = s.scalar(
            select(Invitation).where(
                Invitation.project_id == proj.id,
                Invitation.id == inv_id,
            )
        )
        if inv is None:
            raise HTTPException(404, "invitation not found")
        s.delete(inv)
        s.flush()
        return {"revoked": inv_id}

    @app.post(
        "/invitations/{token}/accept",
        dependencies=[Depends(deps.authz["resolve_identity"])],
    )
    def accept_invitation(
        token: str,
        identity: auth.Identity = Depends(deps.authz["resolve_identity"]),
        s: Session = Depends(deps.db),
    ) -> dict:
        """Accept an invitation (FR-PLAT-3). A share link stays valid for
        everyone who clicks it until it expires or is revoked."""
        sub = identity.sub
        inv = s.scalar(select(Invitation).where(Invitation.token == token))
        if inv is None:
            raise HTTPException(
                404,
                "invitation not found. It may have expired or been revoked",
            )
        if inv.expires_at:
            try:
                exp = datetime.fromisoformat(inv.expires_at)
                if deps.clock() > exp:
                    raise HTTPException(
                        410,
                        "this invitation has expired. Ask the project owner "
                        "to send a new one",
                    )
            except (ValueError, TypeError):
                pass
        inv.accepted_at = deps.now()
        existing = s.scalar(
            select(Membership).where(
                Membership.project_id == inv.project_id, Membership.identity_sub == sub
            )
        )
        if existing is None:
            s.add(
                Membership(
                    project_id=inv.project_id,
                    identity_sub=sub,
                    role=inv.role,
                    invited_by=inv.id,
                    joined_at=deps.now(),
                )
            )
        proj = s.scalar(select(Project).where(Project.id == inv.project_id))
        s.flush()
        return {
            "projectSlug": proj.slug if proj else "",
            "role": existing.role if existing else inv.role,
        }

    def _profile_prefs(s: Session, sub: str) -> dict:
        """The persisted prefs for ``sub`` (FR-OPS-7)."""
        row = s.get(UserProfile, sub)
        return dict(row.prefs) if row is not None else {}

    @app.get("/me", dependencies=[Depends(deps.authz["resolve_identity"])])
    def get_me(
        identity: auth.Identity = Depends(deps.authz["resolve_identity"]),
    ) -> dict:
        """Identity + memberships + preferences (FR-OPS-7)."""
        sub = identity.sub
        mode = identity.mode
        display = identity.display_name
        s = deps.session_factory()
        try:
            rows = s.execute(
                select(Project, Membership.role)
                .join(Membership, Membership.project_id == Project.id)
                .where(Membership.identity_sub == sub)
            ).all()
            return {
                "sub": sub,
                "displayName": display,
                "mode": mode,
                "memberships": [
                    {"projectSlug": p.slug, "projectName": p.name, "role": r}
                    for p, r in rows
                ],
                "preferences": _profile_prefs(s, sub),
            }
        finally:
            s.close()

    KNOWN_PREF_KEYS = frozenset({"theme", "savedViews"})

    @app.put(
        "/me/preferences",
        dependencies=[Depends(deps.authz["resolve_identity"])],
    )
    def put_preferences(
        body: dict,
        identity: auth.Identity = Depends(deps.authz["resolve_identity"]),
        s: Session = Depends(deps.db),
    ) -> dict:
        """Persist this identity's profile preferences (FR-OPS-7)."""
        sub = identity.sub
        incoming = body.get("preferences", body)
        if not isinstance(incoming, dict):
            raise HTTPException(400, "preferences must be an object")
        clean = {k: v for k, v in incoming.items() if k in KNOWN_PREF_KEYS}
        row = s.get(UserProfile, sub)
        if row is None:
            row = UserProfile(
                identity_sub=sub,
                prefs=clean,
                updated_at=deps.now(),
            )
            s.add(row)
        else:
            merged = dict(row.prefs)
            merged.update(clean)
            row.prefs = merged
            row.updated_at = deps.now()
        s.flush()
        return {"sub": sub, "preferences": dict(row.prefs)}
