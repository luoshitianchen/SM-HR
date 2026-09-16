"""HR 域仓储：员工档案/考勤/异动/请假异步数据访问。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hr import AttendanceRecord, ChangeRequest, EmployeeProfile, LeaveRequest


# ── 员工档案 ──
async def get_profile(session: AsyncSession, profile_id: str) -> EmployeeProfile | None:
    result = await session.execute(select(EmployeeProfile).where(EmployeeProfile.id == profile_id))
    return result.scalar_one_or_none()


async def get_profile_by_emp_no(session: AsyncSession, emp_no: str) -> EmployeeProfile | None:
    result = await session.execute(select(EmployeeProfile).where(EmployeeProfile.emp_no == emp_no))
    return result.scalar_one_or_none()


async def list_profiles(session: AsyncSession, limit: int, offset: int,
                       status: str | None = None, keyword: str | None = None) -> list[EmployeeProfile]:
    stmt = select(EmployeeProfile).order_by(EmployeeProfile.hire_date.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(EmployeeProfile.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(EmployeeProfile.name.like(like), EmployeeProfile.emp_no.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_profiles(session: AsyncSession, status: str | None = None,
                        keyword: str | None = None) -> int:
    stmt = select(func.count(EmployeeProfile.id))
    if status:
        stmt = stmt.where(EmployeeProfile.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(EmployeeProfile.name.like(like), EmployeeProfile.emp_no.like(like)))
    return int((await session.execute(stmt)).scalar_one())


async def create_profile(session: AsyncSession, p: EmployeeProfile) -> EmployeeProfile:
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def update_profile(session: AsyncSession, p: EmployeeProfile) -> EmployeeProfile:
    await session.commit()
    await session.refresh(p)
    return p


# ── 考勤 ──
async def get_attendance(session: AsyncSession, rec_id: str) -> AttendanceRecord | None:
    result = await session.execute(select(AttendanceRecord).where(AttendanceRecord.id == rec_id))
    return result.scalar_one_or_none()


async def get_attendance_by_date(session: AsyncSession, employee_id: str,
                                 att_date: date) -> AttendanceRecord | None:
    result = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id, AttendanceRecord.att_date == att_date
        )
    )
    return result.scalar_one_or_none()


async def list_attendance(session: AsyncSession, limit: int, offset: int,
                          employee_id: str | None = None,
                          status: str | None = None) -> list[AttendanceRecord]:
    stmt = select(AttendanceRecord).order_by(AttendanceRecord.att_date.desc()).limit(limit).offset(offset)
    if employee_id:
        stmt = stmt.where(AttendanceRecord.employee_id == employee_id)
    if status:
        stmt = stmt.where(AttendanceRecord.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_attendance(session: AsyncSession, employee_id: str | None = None,
                           status: str | None = None) -> int:
    stmt = select(func.count(AttendanceRecord.id))
    if employee_id:
        stmt = stmt.where(AttendanceRecord.employee_id == employee_id)
    if status:
        stmt = stmt.where(AttendanceRecord.status == status)
    return int((await session.execute(stmt)).scalar_one())


async def create_attendance(session: AsyncSession, rec: AttendanceRecord) -> AttendanceRecord:
    session.add(rec)
    await session.commit()
    await session.refresh(rec)
    return rec


# ── 异动单 ──
async def get_change(session: AsyncSession, change_id: str) -> ChangeRequest | None:
    result = await session.execute(select(ChangeRequest).where(ChangeRequest.id == change_id))
    return result.scalar_one_or_none()


async def list_changes(session: AsyncSession, limit: int, offset: int,
                       status: str | None = None,
                       change_type: str | None = None) -> list[ChangeRequest]:
    stmt = select(ChangeRequest).order_by(ChangeRequest.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(ChangeRequest.status == status)
    if change_type:
        stmt = stmt.where(ChangeRequest.change_type == change_type)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_changes(session: AsyncSession, status: str | None = None,
                        change_type: str | None = None) -> int:
    stmt = select(func.count(ChangeRequest.id))
    if status:
        stmt = stmt.where(ChangeRequest.status == status)
    if change_type:
        stmt = stmt.where(ChangeRequest.change_type == change_type)
    return int((await session.execute(stmt)).scalar_one())


async def create_change(session: AsyncSession, c: ChangeRequest) -> ChangeRequest:
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def update_change(session: AsyncSession, c: ChangeRequest) -> ChangeRequest:
    await session.commit()
    await session.refresh(c)
    return c


# ── 请假单 ──
async def get_leave(session: AsyncSession, leave_id: str) -> LeaveRequest | None:
    result = await session.execute(select(LeaveRequest).where(LeaveRequest.id == leave_id))
    return result.scalar_one_or_none()


async def list_leaves(session: AsyncSession, limit: int, offset: int,
                      status: str | None = None,
                      employee_id: str | None = None) -> list[LeaveRequest]:
    stmt = select(LeaveRequest).order_by(LeaveRequest.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    if employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_leaves(session: AsyncSession, status: str | None = None,
                       employee_id: str | None = None) -> int:
    stmt = select(func.count(LeaveRequest.id))
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    if employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    return int((await session.execute(stmt)).scalar_one())


async def create_leave(session: AsyncSession, lv: LeaveRequest) -> LeaveRequest:
    session.add(lv)
    await session.commit()
    await session.refresh(lv)
    return lv


async def update_leave(session: AsyncSession, lv: LeaveRequest) -> LeaveRequest:
    await session.commit()
    await session.refresh(lv)
    return lv
