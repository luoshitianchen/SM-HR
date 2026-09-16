"""HR 域服务：员工档案、考勤、入转调离、请假的业务规则与状态机。"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from app.core.security import internal_write_allowed
from app.models.hr import AttendanceRecord, ChangeRequest, EmployeeProfile, LeaveRequest
from app.repositories import hr as repo
from app.schemas.hr import (
    AttendanceCreate,
    ChangeCreate,
    LeaveCreate,
    ProfileCreate,
)
from app.services.audit import record_audit

# 员工档案合法状态迁移
_PROFILE_TRANSITIONS: dict[str, set[str]] = {
    "probation": {"regular", "left"},
    "regular": {"left"},
    "left": set(),
}
# 异动单合法状态迁移
_CHANGE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"approved", "rejected"},
    "approved": {"completed", "rejected"},
    "completed": set(),
    "rejected": set(),
}
# 请假单合法状态迁移
_LEAVE_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"approved", "rejected"},
    "approved": set(),
    "rejected": set(),
}
_CHANGE_ACTION = {"approve": "approved", "reject": "rejected", "complete": "completed"}
_LEAVE_ACTION = {"approve": "approved", "reject": "rejected"}


def _profile_to_dict(p: EmployeeProfile) -> dict:
    return {
        "id": p.id, "emp_no": p.emp_no, "name": p.name, "department": p.department,
        "position": p.position, "phone": p.phone,
        "hire_date": p.hire_date.isoformat() if p.hire_date else "",
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
    }


def _att_to_dict(r: AttendanceRecord) -> dict:
    return {
        "id": r.id, "employee_id": r.employee_id, "att_date": r.att_date.isoformat() if r.att_date else "",
        "status": r.status,
        "check_in": r.check_in.isoformat() if r.check_in else None,
        "check_out": r.check_out.isoformat() if r.check_out else None,
        "remark": r.remark,
    }


def _change_to_dict(c: ChangeRequest) -> dict:
    return {
        "id": c.id, "employee_id": c.employee_id, "change_type": c.change_type,
        "from_department": c.from_department, "to_department": c.to_department,
        "effective_date": c.effective_date.isoformat() if c.effective_date else "",
        "reason": c.reason, "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else "",
    }


def _leave_to_dict(lv: LeaveRequest) -> dict:
    return {
        "id": lv.id, "employee_id": lv.employee_id, "leave_type": lv.leave_type,
        "start_date": lv.start_date.isoformat() if lv.start_date else "",
        "end_date": lv.end_date.isoformat() if lv.end_date else "",
        "days": lv.days, "reason": lv.reason, "status": lv.status,
        "created_at": lv.created_at.isoformat() if lv.created_at else "",
    }


class ProfileService:
    @staticmethod
    async def list_profiles(session, limit, offset, status_filter, keyword):
        rows = await repo.list_profiles(session, limit, offset, status_filter, keyword)
        total = await repo.count_profiles(session, status_filter, keyword)
        return {"total": total, "items": [_profile_to_dict(p) for p in rows]}

    @staticmethod
    async def get_profile(session, profile_id):
        p = await repo.get_profile(session, profile_id)
        if not p:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "员工档案不存在")
        return _profile_to_dict(p)

    @staticmethod
    async def create_profile(session, payload: ProfileCreate, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        # 业务规则：入职日期不得晚于今天
        if payload.hire_date > date.today():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "入职日期不能晚于今天")
        if await repo.get_profile_by_emp_no(session, payload.emp_no):
            raise HTTPException(status.HTTP_409_CONFLICT, "工号已存在")
        p = EmployeeProfile(
            id=str(uuid.uuid4()), emp_no=payload.emp_no, name=payload.name,
            department=payload.department, position=payload.position, phone=payload.phone,
            hire_date=payload.hire_date, status="probation",
        )
        try:
            p = await repo.create_profile(session, p)
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "工号已存在") from exc
        await record_audit(session, "hr.profile.created", "internal",
                           f"profile_id={p.id} emp_no={payload.emp_no}", request)
        return _profile_to_dict(p)

    @staticmethod
    async def change_status(session, profile_id, new_status, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        p = await repo.get_profile(session, profile_id)
        if not p:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "员工档案不存在")
        if new_status not in _PROFILE_TRANSITIONS.get(p.status, set()):
            raise HTTPException(status.HTTP_409_CONFLICT,
                               f"员工状态 {p.status} 不可流转为 {new_status}")
        p.status = new_status
        p = await repo.update_profile(session, p)
        await record_audit(session, "hr.profile.status_changed", "internal",
                           f"profile_id={profile_id} status={new_status}", request)
        return _profile_to_dict(p)


class AttendanceService:
    @staticmethod
    async def list_records(session, limit, offset, employee_id, status_filter):
        rows = await repo.list_attendance(session, limit, offset, employee_id, status_filter)
        total = await repo.count_attendance(session, employee_id, status_filter)
        return {"total": total, "items": [_att_to_dict(r) for r in rows]}

    @staticmethod
    async def create_record(session, payload: AttendanceCreate, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if not await repo.get_profile(session, payload.employee_id):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "员工不存在")
        # 业务规则：签到时间必须早于签退时间
        if payload.check_in and payload.check_out and payload.check_in >= payload.check_out:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "签到时间必须早于签退时间")
        rec = AttendanceRecord(
            id=str(uuid.uuid4()), employee_id=payload.employee_id, att_date=payload.att_date,
            status=payload.status, check_in=payload.check_in, check_out=payload.check_out,
            remark=payload.remark,
        )
        try:
            rec = await repo.create_attendance(session, rec)
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "该员工当日考勤已存在") from exc
        await record_audit(session, "hr.attendance.created", "internal",
                           f"att_id={rec.id} date={payload.att_date}", request)
        return _att_to_dict(rec)


class ChangeService:
    @staticmethod
    async def list_changes(session, limit, offset, status_filter, change_type):
        rows = await repo.list_changes(session, limit, offset, status_filter, change_type)
        total = await repo.count_changes(session, status_filter, change_type)
        return {"total": total, "items": [_change_to_dict(c) for c in rows]}

    @staticmethod
    async def create_change(session, payload: ChangeCreate, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        profile = await repo.get_profile(session, payload.employee_id)
        if not profile:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "员工不存在")
        # 业务规则：生效日期不得早于今天
        if payload.effective_date < date.today():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "生效日期不能早于今天")
        # 离职仅适用于在职员工
        if payload.change_type == "resign" and profile.status == "left":
            raise HTTPException(status.HTTP_409_CONFLICT, "员工已离职，不可再次发起离职")
        c = ChangeRequest(
            id=str(uuid.uuid4()), employee_id=payload.employee_id,
            change_type=payload.change_type, from_department=payload.from_department,
            to_department=payload.to_department, effective_date=payload.effective_date,
            reason=payload.reason, status="draft",
        )
        c = await repo.create_change(session, c)
        await record_audit(session, "hr.change.created", "internal",
                           f"change_id={c.id} type={payload.change_type}", request)
        return _change_to_dict(c)

    @staticmethod
    async def transition(session, change_id, action, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        c = await repo.get_change(session, change_id)
        if not c:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "异动单不存在")
        target = _CHANGE_ACTION[action]
        if target not in _CHANGE_TRANSITIONS.get(c.status, set()):
            raise HTTPException(status.HTTP_409_CONFLICT,
                               f"异动单状态 {c.status} 不允许执行 {action}")
        c.status = target
        c = await repo.update_change(session, c)
        # 完成离职异动时联动员工档案状态
        if action == "complete" and c.change_type == "resign":
            profile = await repo.get_profile(session, c.employee_id)
            if profile:
                profile.status = "left"
                await repo.update_profile(session, profile)
        await record_audit(session, "hr.change.transition", "internal",
                           f"change_id={change_id} action={action}", request)
        return _change_to_dict(c)


class LeaveService:
    @staticmethod
    async def list_leaves(session, limit, offset, status_filter, employee_id):
        rows = await repo.list_leaves(session, limit, offset, status_filter, employee_id)
        total = await repo.count_leaves(session, status_filter, employee_id)
        return {"total": total, "items": [_leave_to_dict(lv) for lv in rows]}

    @staticmethod
    async def create_leave(session, payload: LeaveCreate, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if not await repo.get_profile(session, payload.employee_id):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "员工不存在")
        # 业务规则：开始日期不得晚于结束日期
        if payload.start_date > payload.end_date:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "开始日期不能晚于结束日期")
        lv = LeaveRequest(
            id=str(uuid.uuid4()), employee_id=payload.employee_id,
            leave_type=payload.leave_type, start_date=payload.start_date,
            end_date=payload.end_date, days=payload.days, reason=payload.reason,
            status="draft",
        )
        lv = await repo.create_leave(session, lv)
        await record_audit(session, "hr.leave.created", "internal",
                           f"leave_id={lv.id} days={payload.days}", request)
        return _leave_to_dict(lv)

    @staticmethod
    async def transition(session, leave_id, action, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        lv = await repo.get_leave(session, leave_id)
        if not lv:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "请假单不存在")
        target = _LEAVE_ACTION[action]
        if target not in _LEAVE_TRANSITIONS.get(lv.status, set()):
            raise HTTPException(status.HTTP_409_CONFLICT,
                               f"请假单状态 {lv.status} 不允许执行 {action}")
        lv.status = target
        lv = await repo.update_leave(session, lv)
        await record_audit(session, "hr.leave.transition", "internal",
                           f"leave_id={leave_id} action={action}", request)
        return _leave_to_dict(lv)
