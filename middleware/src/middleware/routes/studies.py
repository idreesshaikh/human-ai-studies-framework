"""Study-first routes for the researcher's study list and workspace."""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import auth
from middleware.db import Membership, Project, Study
from middleware.routes.deps import ApiDeps


def _summary(
    study: Study, project: Project, role: str, deps: ApiDeps, s: Session
) -> dict:
    protocol = deps.resolve_study_protocol(s, study.id)
    title = ((protocol or {}).get("study") or {}).get("title")
    return {
        "id": study.id,
        # The name typed at creation; older studies fall back to the applied
        # protocol's title, and the client to the id as words.
        "name": study.name or (title if isinstance(title, str) else "") or "",
        "projectSlug": project.slug,
        "hasProtocol": protocol is not None,
        "role": role,
    }


def register(app: FastAPI, deps: ApiDeps) -> None:
    identity_dependency = deps.authz["resolve_identity"]

    @app.get("/studies")
    def list_studies(
        identity: auth.Identity = Depends(identity_dependency),
        s: Session = Depends(deps.db),
    ) -> list[dict]:
        """List only studies visible to the current researcher."""
        rows = s.execute(
            select(Study, Project, Membership.role)
            .join(Project, Project.id == Study.project_id)
            .join(Membership, Membership.project_id == Project.id)
            .where(Membership.identity_sub == identity.sub)
        ).all()
        return [
            _summary(study, project, role, deps, s) for study, project, role in rows
        ]

    @app.get("/studies/{study_id}/summary")
    def study_summary(
        study_id: str,
        membership: Membership = Depends(
            deps.authz["require_project_for_study"]("view")
        ),
        s: Session = Depends(deps.db),
    ) -> dict:
        """Return the small amount of study metadata needed by its workspace."""
        study = s.get(Study, study_id)
        if study is None:
            raise HTTPException(404, "study not found")
        project = s.get(Project, study.project_id)
        if project is None:
            raise HTTPException(404, "study not found")
        return _summary(study, project, membership.role, deps, s)
