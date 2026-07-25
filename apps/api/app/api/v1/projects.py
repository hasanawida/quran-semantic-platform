"""مسارات المشاريع والتقارير (المرحلة F)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import get_session
from app.models.project import ProjectRole, ProjectVisibility
from app.models.user import User
from app.services.project import ProjectError, ProjectService

router = APIRouter(tags=["Projects"])

_STATUS_BY_CODE = {
    "PROJECT_NOT_FOUND": 404,
    "REPORT_NOT_FOUND": 404,
    "VERSION_NOT_FOUND": 404,
    "CLAIM_NOT_FOUND": 404,
    "USER_NOT_FOUND": 404,
    "PROJECT_FORBIDDEN": 403,
    "CLAIM_ALREADY_IN_PROJECT": 409,
    "NO_APPROVED_CLAIMS": 409,
    "NO_CHANGES": 409,
    "TITLE_REQUIRED": 422,
}


def _err(exc: ProjectError) -> HTTPException:
    return HTTPException(
        status_code=_STATUS_BY_CODE.get(exc.code, 400),
        detail={"code": exc.code, "message": exc.message},
    )


class ProjectRequest(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    visibility: ProjectVisibility = ProjectVisibility.PRIVATE


class MemberRequest(BaseModel):
    user_id: str
    role: ProjectRole = ProjectRole.VIEWER


class ClaimRefRequest(BaseModel):
    claim_id: str


class ReportRequest(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    summary: str | None = Field(default=None, max_length=4000)


class PublishRequest(BaseModel):
    change_note: str | None = Field(default=None, max_length=1000)


@router.get("/projects")
async def list_projects(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return ok(request, await ProjectService(session).list_projects(user))


@router.post("/projects")
async def create_project(
    request: Request,
    body: ProjectRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ProjectService(session).create_project(
            body.model_dump(), user.id
        )
    except ProjectError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.get("/projects/{project_id}")
async def get_project(
    request: Request,
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ProjectService(session).get_project(project_id, user)
    except ProjectError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/projects/{project_id}/members")
async def set_member(
    request: Request,
    project_id: uuid.UUID,
    body: MemberRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ProjectService(session).add_member(
            project_id, uuid.UUID(body.user_id), body.role.value, user
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "معرف مستخدم غير صالح."},
        ) from None
    except ProjectError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/projects/{project_id}/claims")
async def add_claim_to_project(
    request: Request,
    project_id: uuid.UUID,
    body: ClaimRefRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ProjectService(session).add_claim(
            project_id, uuid.UUID(body.claim_id), user
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "معرف ادعاء غير صالح."},
        ) from None
    except ProjectError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/projects/{project_id}/reports")
async def create_report(
    request: Request,
    project_id: uuid.UUID,
    body: ReportRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ProjectService(session).create_report(
            project_id, body.title, body.summary, user
        )
    except ProjectError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.get("/reports/{report_id}")
async def get_report(
    request: Request,
    report_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ProjectService(session).get_report(report_id, user)
    except ProjectError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/reports/{report_id}/publish")
async def publish_report(
    request: Request,
    report_id: uuid.UUID,
    body: PublishRequest | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ProjectService(session).publish_report_version(
            report_id, user, body.change_note if body else None
        )
    except ProjectError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.get("/report-versions/{version_id}")
async def get_report_version(
    request: Request,
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ProjectService(session).get_report_version(version_id, user)
    except ProjectError as exc:
        raise _err(exc) from None
    return ok(request, result)
