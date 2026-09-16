"""HR 域 Pydantic 模型。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    emp_no: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=80)
    department: str = Field(default="", max_length=64)
    position: str = Field(default="", max_length=64)
    phone: str = Field(default="", max_length=32)
    hire_date: date


class ProfileStatusUpdate(BaseModel):
    status: Literal["probation", "regular", "left"]


class AttendanceCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=64)
    att_date: date
    status: Literal["present", "late", "absent", "leave"] = "present"
    check_in: datetime | None = None
    check_out: datetime | None = None
    remark: str = Field(default="", max_length=256)


class ChangeCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=64)
    change_type: Literal["join", "transfer", "promotion", "resign"]
    from_department: str = Field(default="", max_length=64)
    to_department: str = Field(default="", max_length=64)
    effective_date: date
    reason: str = Field(default="", max_length=512)


class ChangeTransition(BaseModel):
    action: Literal["approve", "reject", "complete"]


class LeaveCreate(BaseModel):
    employee_id: str = Field(min_length=1, max_length=64)
    leave_type: Literal["personal", "sick", "annual"]
    start_date: date
    end_date: date
    days: float = Field(gt=0)
    reason: str = Field(default="", max_length=512)


class LeaveTransition(BaseModel):
    action: Literal["approve", "reject"]
