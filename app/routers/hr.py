"""HR 域路由：员工档案、考勤、入转调离、请假。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.hr import (
    AttendanceCreate,
    ChangeCreate,
    ChangeTransition,
    LeaveCreate,
    LeaveTransition,
    ProfileCreate,
    ProfileStatusUpdate,
)
from app.services.hr import AttendanceService, ChangeService, LeaveService, ProfileService

router = APIRouter(prefix="/api/hr", tags=["hr-core"])


# ── 员工档案 ──
@router.get("/profiles")
async def list_profiles(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ProfileService.list_profiles(session, limit, offset, status_filter, keyword)


@router.post("/profiles", status_code=status.HTTP_201_CREATED)
async def create_profile(
    payload: ProfileCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ProfileService.create_profile(session, payload, request)


@router.get("/profiles/{profile_id}")
async def get_profile(
    profile_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ProfileService.get_profile(session, profile_id)


@router.patch("/profiles/{profile_id}/status")
async def change_profile_status(
    profile_id: str, payload: ProfileStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ProfileService.change_status(session, profile_id, payload.status, request)


# ── 考勤 ──
@router.get("/attendance")
async def list_attendance(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    employee_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AttendanceService.list_records(session, limit, offset, employee_id, status_filter)


@router.post("/attendance", status_code=status.HTTP_201_CREATED)
async def create_attendance(
    payload: AttendanceCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AttendanceService.create_record(session, payload, request)


# ── 异动 ──
@router.get("/changes")
async def list_changes(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    change_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ChangeService.list_changes(session, limit, offset, status_filter, change_type)


@router.post("/changes", status_code=status.HTTP_201_CREATED)
async def create_change(
    payload: ChangeCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ChangeService.create_change(session, payload, request)


@router.patch("/changes/{change_id}/transition")
async def transition_change(
    change_id: str, payload: ChangeTransition, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ChangeService.transition(session, change_id, payload.action, request)


# ── 请假 ──
@router.get("/leaves")
async def list_leaves(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    employee_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await LeaveService.list_leaves(session, limit, offset, status_filter, employee_id)


@router.post("/leaves", status_code=status.HTTP_201_CREATED)
async def create_leave(
    payload: LeaveCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await LeaveService.create_leave(session, payload, request)


@router.patch("/leaves/{leave_id}/transition")
async def transition_leave(
    leave_id: str, payload: LeaveTransition, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await LeaveService.transition(session, leave_id, payload.action, request)
